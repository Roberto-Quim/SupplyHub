-- =============================================================
-- 020_create_sp_module_writes.sql
-- Procedimientos almacenados de ESCRITURA de Módulos y Submódulos (fase 8).
--
-- Crea (idempotente, CREATE OR ALTER) SOLO escrituras "normales" de dbo.Modulos y
-- dbo.Submodulo. NO incluye DELETE de submódulos ni cascadas (delete_submodulo sigue
-- 100% en Python). NO crea tablas ni cambia datos por sí solo.
--
--   dbo.AddOrUpdModuloAdminDAsp      → upsert de módulo (create_modulo / update_modulo).
--   dbo.UpdModuloActivoAdminDAsp     → activa/desactiva módulo (set_modulo_active).
--   dbo.AddOrUpdSubmoduloAdminDAsp   → upsert de submódulo (create_submodulo / update_submodulo).
--   dbo.UpdSubmoduloActivoAdminDAsp  → activa/desactiva submódulo (set_submodulo_active).
--
-- PRINCIPIO DE SEGURIDAD: la AUTORIZACIÓN/JERARQUÍA (TI/Administrador/Usuario) y las
-- VALIDACIONES (nombre requerido, módulo padre existente/activo, nombre duplicado, valor
-- técnico '#' para padres) VIVEN EN PYTHON (dataanalytics_modulos_service.py). Estos SPs
-- solo ejecutan la operación de datos ya autorizada y validada. Por eso los upsert reciben
-- @IdModulo/@IdSubModulo (NULL=alta, valor=edición): NO re-resuelven existencia ni permisos.
--
-- AUTO-PERMISO TI: al crear un submódulo, el auto-permiso del PERFIL TI en dbo.PerfilModulos
-- se mantiene EN PYTHON (misma transacción, sin migrar) — estos SPs NO tocan PerfilModulos.
--
-- El módulo padre no navega: si no se entrega Ruta, el servicio ya envía '#'. El SP inserta
-- @Ruta tal cual lo recibe (no calcula el '#').
--
-- ORDEN DE EJECUCIÓN EN BD:
--   1. Tablas base (Modulos, Submodulo) ya migradas (007+).
--   2. 020_create_sp_module_writes.sql (este archivo, fase 8).
--
-- ⚠️  NO EJECUTAR SIN AUTORIZACIÓN del Ing./DBA. Este archivo solo versiona el DDL.
-- =============================================================

USE DataAnalytics;
GO

/*
    Nombre:        AddOrUpdModuloAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Upsert de módulo. Si @IdModulo es NULL, INSERTA (Activo=1,
                   FechaAdd/FechaUpd=GETDATE()) y devuelve el nuevo IdModulo. Si @IdModulo
                   viene, ACTUALIZA Modulo/Ruta/Orden y FechaUpd. El servicio ya validó
                   jerarquía, nombre requerido y nombre duplicado, y ya calculó @Ruta.
    Parámetros:    @IdModulo BIGINT = NULL  (NULL = alta; valor = edición),
                   @Modulo NVARCHAR(150), @Ruta NVARCHAR(255), @Orden INT
    Retorno:       En alta: result set de una fila con IdModulo (SCOPE_IDENTITY()).
                   En edición: sin result set.
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.AddOrUpdModuloAdminDAsp
    @IdModulo BIGINT        = NULL,
    @Modulo   NVARCHAR(150),
    @Ruta     NVARCHAR(255),
    @Orden    INT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        IF @IdModulo IS NULL
        BEGIN
            INSERT INTO dbo.Modulos (Modulo, Ruta, Orden, Activo, FechaAdd, FechaUpd)
            VALUES (@Modulo, @Ruta, @Orden, 1, GETDATE(), GETDATE());

            SELECT CAST(SCOPE_IDENTITY() AS BIGINT) AS IdModulo;
        END
        ELSE
        BEGIN
            UPDATE dbo.Modulos
            SET Modulo = @Modulo, Ruta = @Ruta, Orden = @Orden, FechaUpd = GETDATE()
            WHERE IdModulo = @IdModulo;
        END
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        UpdModuloActivoAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Activa o desactiva (lógico) un módulo. Actualiza FechaUpd. No borra físico.
    Parámetros:    @IdModulo BIGINT, @Activo BIT
    Retorno:       (sin result set) — el servicio devuelve True/False según commit.
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.UpdModuloActivoAdminDAsp
    @IdModulo BIGINT,
    @Activo   BIT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        UPDATE dbo.Modulos
        SET Activo = @Activo, FechaUpd = GETDATE()
        WHERE IdModulo = @IdModulo;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        AddOrUpdSubmoduloAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Upsert de submódulo. Si @IdSubModulo es NULL, INSERTA bajo @IdModulo
                   (Activo=1) y devuelve el nuevo IdSubModulo. Si @IdSubModulo viene,
                   ACTUALIZA SubModulo/Ruta/Orden y FechaUpd (NO cambia de módulo padre;
                   @IdModulo se ignora en edición). El servicio ya validó módulo padre y
                   nombre duplicado. El auto-permiso TI se maneja aparte (en Python).
    Parámetros:    @IdSubModulo BIGINT = NULL  (NULL = alta; valor = edición),
                   @IdModulo BIGINT = NULL      (requerido solo en alta),
                   @SubModulo NVARCHAR(150), @Ruta NVARCHAR(255), @Orden INT
    Retorno:       En alta: result set de una fila con IdSubModulo (SCOPE_IDENTITY()).
                   En edición: sin result set.
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.AddOrUpdSubmoduloAdminDAsp
    @IdSubModulo BIGINT       = NULL,
    @IdModulo    BIGINT       = NULL,
    @SubModulo   NVARCHAR(150),
    @Ruta        NVARCHAR(255),
    @Orden       INT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        IF @IdSubModulo IS NULL
        BEGIN
            INSERT INTO dbo.Submodulo (IdModulo, SubModulo, Ruta, Orden, Activo, FechaAdd, FechaUpd)
            VALUES (@IdModulo, @SubModulo, @Ruta, @Orden, 1, GETDATE(), GETDATE());

            SELECT CAST(SCOPE_IDENTITY() AS BIGINT) AS IdSubModulo;
        END
        ELSE
        BEGIN
            UPDATE dbo.Submodulo
            SET SubModulo = @SubModulo, Ruta = @Ruta, Orden = @Orden, FechaUpd = GETDATE()
            WHERE IdSubModulo = @IdSubModulo;
        END
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        UpdSubmoduloActivoAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Activa o desactiva (lógico) un submódulo. Actualiza FechaUpd. No borra físico.
    Parámetros:    @IdSubModulo BIGINT, @Activo BIT
    Retorno:       (sin result set) — el servicio devuelve True/False según commit.
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.UpdSubmoduloActivoAdminDAsp
    @IdSubModulo BIGINT,
    @Activo      BIT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        UPDATE dbo.Submodulo
        SET Activo = @Activo, FechaUpd = GETDATE()
        WHERE IdSubModulo = @IdSubModulo;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

-- ── Verificación (opcional, solo lectura) ────────────────────────
PRINT '020: SPs de escritura de Módulos/Submódulos creados/actualizados.';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name IN ('AddOrUpdModuloAdminDAsp','UpdModuloActivoAdminDAsp',
               'AddOrUpdSubmoduloAdminDAsp','UpdSubmoduloActivoAdminDAsp')
ORDER BY name;
GO
