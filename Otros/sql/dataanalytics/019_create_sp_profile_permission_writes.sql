-- =============================================================
-- 019_create_sp_profile_permission_writes.sql
-- Procedimientos almacenados de ESCRITURA de Perfiles y asignaciones PerfilModulos (fase 7).
--
-- Crea (idempotente, CREATE OR ALTER) SOLO escrituras de PERFILES y de sus asignaciones
-- de submódulos en dbo.PerfilModulos. NO toca escrituras de Módulos/Submódulos, ni delete
-- de módulos/submódulos, ni ninguna otra tabla. NO crea tablas ni cambia datos por sí solo.
--
--   dbo.AddOrUpdPerfilAdminDAsp      → upsert del perfil (create_profile / update_profile).
--   dbo.UpdPerfilActivoAdminDAsp     → activa/desactiva un perfil (set_profile_active).
--   dbo.SetPerfilSubmodulosAdminDAsp → reemplazo lógico de asignaciones (_upsert_asignaciones).
--
-- PRINCIPIO DE SEGURIDAD: la AUTORIZACIÓN/JERARQUÍA (TI/Administrador/Usuario, actor,
-- system) y los chequeos de nombre duplicado / existencia del perfil VIVEN EN PYTHON
-- (dataanalytics_perfiles_service.py). Estos SPs solo ejecutan la operación de datos ya
-- autorizada por el servicio. Por eso AddOrUpdPerfilAdminDAsp recibe @IdPerfil (NULL=alta,
-- valor=edición): NO re-resuelve existencia ni permisos.
--
-- SetPerfilSubmodulosAdminDAsp recibe las asignaciones como CSV de enteros y conserva la
-- lógica actual: valida que todos existan y estén ACTIVOS (rechaza inválidos/inactivos con
-- RAISERROR), desactiva las removidas, reactiva las existentes e inserta las nuevas (sin
-- duplicar). Un CSV vacío/NULL desactiva TODAS las asignaciones del perfil (igual que hoy).
--
-- ORDEN DE EJECUCIÓN EN BD:
--   1. Tablas base (Perfiles, Submodulo, PerfilModulos) ya migradas (007+).
--   2. 018_create_sp_profile_permission_reads.sql (lecturas, fase 6).
--   3. 019_create_sp_profile_permission_writes.sql (este archivo, fase 7).
--
-- ⚠️  NO EJECUTAR SIN AUTORIZACIÓN del Ing./DBA. Este archivo solo versiona el DDL.
-- =============================================================

USE DataAnalytics;
GO

/*
    Nombre:        AddOrUpdPerfilAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Upsert de perfil. Si @IdPerfil es NULL, INSERTA (Activo=1,
                   FechaAdd/FechaUpd=GETDATE()) y devuelve el nuevo IdPerfil. Si @IdPerfil
                   viene, ACTUALIZA el nombre (Perfil) y FechaUpd. El servicio ya validó
                   jerarquía, existencia y nombre duplicado.
    Parámetros:    @IdPerfil BIGINT = NULL  (NULL = alta; valor = edición),
                   @Perfil NVARCHAR(100)
    Retorno:       En alta: result set de una fila con IdPerfil (SCOPE_IDENTITY()).
                   En edición: sin result set.
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.AddOrUpdPerfilAdminDAsp
    @IdPerfil BIGINT        = NULL,
    @Perfil   NVARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        IF @IdPerfil IS NULL
        BEGIN
            INSERT INTO dbo.Perfiles (Perfil, Activo, FechaAdd, FechaUpd)
            VALUES (@Perfil, 1, GETDATE(), GETDATE());

            SELECT CAST(SCOPE_IDENTITY() AS BIGINT) AS IdPerfil;
        END
        ELSE
        BEGIN
            UPDATE dbo.Perfiles
            SET Perfil = @Perfil, FechaUpd = GETDATE()
            WHERE IdPerfil = @IdPerfil;
        END
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        UpdPerfilActivoAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Activa o desactiva (lógico) un perfil. Actualiza FechaUpd. No borra
                   físicamente. El servicio ya validó jerarquía.
    Parámetros:    @IdPerfil BIGINT, @Activo BIT
    Retorno:       (sin result set) — el servicio devuelve True/False según commit.
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.UpdPerfilActivoAdminDAsp
    @IdPerfil BIGINT,
    @Activo   BIT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        UPDATE dbo.Perfiles
        SET Activo = @Activo, FechaUpd = GETDATE()
        WHERE IdPerfil = @IdPerfil;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        SetPerfilSubmodulosAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Reemplazo LÓGICO de las asignaciones de submódulos de un perfil en
                   dbo.PerfilModulos (no borra físico). Conserva la lógica del servicio:
                     - Valida que TODOS los @IdSubModulo existan y estén ACTIVOS; si alguno
                       es inválido/inactivo lanza RAISERROR (el servicio hace rollback).
                     - Desactiva las asignaciones removidas (todas si el CSV es vacío/NULL).
                     - Reactiva las existentes seleccionadas e inserta las nuevas (sin duplicar).
                   Recibe los IdSubModulo como CSV de enteros; se dividen con STRING_SPLIT y
                   se convierten con TRY_CAST. NO concatena valores.
    Parámetros:    @IdPerfil BIGINT, @IdSubmodulosCsv NVARCHAR(MAX) = NULL  (p. ej. '1,2,5')
    Retorno:       (sin result set) — el servicio confirma con commit/rollback.
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.SetPerfilSubmodulosAdminDAsp
    @IdPerfil         BIGINT,
    @IdSubmodulosCsv  NVARCHAR(MAX) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        -- Cantidad de tokens pedidos (distintos, no vacíos) para validar exactitud.
        DECLARE @Pedidos INT = (
            SELECT COUNT(*) FROM (
                SELECT DISTINCT LTRIM(RTRIM(value)) AS raw
                FROM STRING_SPLIT(COALESCE(@IdSubmodulosCsv, ''), ',')
                WHERE LTRIM(RTRIM(value)) <> ''
            ) q
        );

        DECLARE @Ids TABLE (Id BIGINT PRIMARY KEY);
        IF @Pedidos > 0
        BEGIN
            INSERT INTO @Ids (Id)
            SELECT DISTINCT TRY_CAST(LTRIM(RTRIM(value)) AS BIGINT)
            FROM STRING_SPLIT(COALESCE(@IdSubmodulosCsv, ''), ',')
            WHERE LTRIM(RTRIM(value)) <> ''
              AND TRY_CAST(LTRIM(RTRIM(value)) AS BIGINT) IS NOT NULL;

            -- Todos deben existir y estar activos (rechaza inválidos/inactivos como hoy).
            DECLARE @Validos INT = (
                SELECT COUNT(*)
                FROM dbo.Submodulo s
                INNER JOIN @Ids i ON i.Id = s.IdSubModulo
                WHERE s.Activo = 1
            );
            IF @Validos <> @Pedidos
            BEGIN
                RAISERROR('Uno o más IdSubModulo no existen o están inactivos.', 16, 1);
                RETURN;
            END
        END

        -- Desactivar las removidas (todas si @Ids está vacío).
        UPDATE dbo.PerfilModulos
        SET Activo = 0, FechaUpd = GETDATE()
        WHERE IdPerfil = @IdPerfil
          AND IdSubModulo NOT IN (SELECT Id FROM @Ids);

        -- Reactivar las seleccionadas que ya existían.
        UPDATE pm
        SET Activo = 1, FechaUpd = GETDATE()
        FROM dbo.PerfilModulos pm
        INNER JOIN @Ids i ON i.Id = pm.IdSubModulo
        WHERE pm.IdPerfil = @IdPerfil;

        -- Insertar las seleccionadas que aún no existían.
        INSERT INTO dbo.PerfilModulos (IdPerfil, IdSubModulo, Activo, FechaAdd, FechaUpd)
        SELECT @IdPerfil, i.Id, 1, GETDATE(), GETDATE()
        FROM @Ids i
        WHERE NOT EXISTS (
            SELECT 1 FROM dbo.PerfilModulos pm
            WHERE pm.IdPerfil = @IdPerfil AND pm.IdSubModulo = i.Id
        );
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

-- ── Verificación (opcional, solo lectura) ────────────────────────
PRINT '019: SPs de escritura de Perfiles/PerfilModulos creados/actualizados.';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name IN ('AddOrUpdPerfilAdminDAsp','UpdPerfilActivoAdminDAsp','SetPerfilSubmodulosAdminDAsp')
ORDER BY name;
GO
