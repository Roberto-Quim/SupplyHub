-- =============================================================
-- 016_create_sp_user_admin_writes.sql
-- Procedimientos almacenados de ESCRITURA de Administración de Usuarios (fase 4B).
--
-- Crea (idempotente, CREATE OR ALTER) SOLO escrituras:
--   dbo.AddOrUpdUsuarioAdminDAsp       → upsert (reemplaza upsert_user).
--   dbo.UpdUsuarioPerfilAccesoAdminDAsp→ cambia perfil/acceso (update_user_profile).
--   dbo.UpdUsuarioActivoAdminDAsp      → activa/desactiva (set_user_active).
--
-- PRINCIPIO DE SEGURIDAD: la AUTORIZACIÓN/JERARQUÍA (TI/Administrador/Usuario, actor,
-- system) vive en Python (dataanalytics_user_admin_service.py). Estos SPs SOLO
-- ejecutan la operación de datos ya autorizada por el servicio. Por eso
-- AddOrUpdUsuarioAdminDAsp recibe @IdUsuario (decidido por Python tras buscar el
-- existente y validar jerarquía): NO re-resuelve existencia ni permisos.
--
-- Esta fase NO migra lecturas (ya en 015), ni plantas, ni Módulos/Submódulos.
-- El script NO cambia datos ni crea tablas: solo crea/actualiza procedimientos. Las
-- escrituras solo ocurren cuando el backend (ya autorizado) los invoca.
--
-- ORDEN DE EJECUCIÓN EN BD:
--   1. Tablas base de Usuarios/Perfiles/Acceso (ya existentes).
--   2. 015_create_sp_user_admin_reads.sql  (lecturas, fase 4A).
--   3. 016_create_sp_user_admin_writes.sql (este archivo, fase 4B).
--
-- ⚠️  NO EJECUTAR SIN AUTORIZACIÓN del Ing./DBA. Este archivo solo versiona el DDL.
-- =============================================================

USE DataAnalytics;
GO

/*
    Nombre:        AddOrUpdUsuarioAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Upsert de usuario. Si @IdUsuario viene (el servicio ya localizó al
                   existente por NoNomina/Correo y validó jerarquía), ACTUALIZA:
                   IdPerfil, IdAcceso, completa NoNomina/Correo si faltan (COALESCE),
                   Activo=1, FechaUpd=GETDATE(). Si @IdUsuario es NULL, INSERTA con
                   Activo=1, FechaAdd/FechaUpd=GETDATE() y devuelve el nuevo IdUsuario.
    Parámetros:    @IdUsuario BIGINT = NULL  (NULL = alta; valor = edición),
                   @NoNomina NVARCHAR(20) = NULL, @Correo NVARCHAR(255) = NULL,
                   @IdPerfil BIGINT, @IdAcceso BIGINT = NULL
    Retorno:       En alta: result set de una fila con IdUsuario (SCOPE_IDENTITY()).
                   En edición: sin result set (el servicio ya conoce el IdUsuario).
                   El servicio decide 'created' por si pasó @IdUsuario o no.
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.AddOrUpdUsuarioAdminDAsp
    @IdUsuario  BIGINT        = NULL,
    @NoNomina   NVARCHAR(20)  = NULL,
    @Correo     NVARCHAR(255) = NULL,
    @IdPerfil   BIGINT,
    @IdAcceso   BIGINT        = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        IF @IdUsuario IS NOT NULL
        BEGIN
            UPDATE dbo.Usuarios SET
                IdPerfil = @IdPerfil,
                IdAcceso = @IdAcceso,
                NoNomina = COALESCE(@NoNomina, NoNomina),
                Correo   = COALESCE(@Correo, Correo),
                Activo   = 1,
                FechaUpd = GETDATE()
            WHERE IdUsuario = @IdUsuario;
        END
        ELSE
        BEGIN
            INSERT INTO dbo.Usuarios (IdPerfil, NoNomina, Correo, IdAcceso, Activo, FechaAdd, FechaUpd)
            VALUES (@IdPerfil, @NoNomina, @Correo, @IdAcceso, 1, GETDATE(), GETDATE());

            SELECT CAST(SCOPE_IDENTITY() AS BIGINT) AS IdUsuario;
        END
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        UpdUsuarioPerfilAccesoAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Cambia el perfil de un usuario y, opcionalmente, su acceso.
                   Si @IdAcceso es NULL, NO toca IdAcceso (solo IdPerfil + FechaUpd),
                   igual que el servicio actual.
    Parámetros:    @IdUsuario BIGINT, @IdPerfil BIGINT, @IdAcceso BIGINT = NULL
    Retorno:       (sin result set) — el servicio devuelve True/False según commit.
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.UpdUsuarioPerfilAccesoAdminDAsp
    @IdUsuario BIGINT,
    @IdPerfil  BIGINT,
    @IdAcceso  BIGINT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        IF @IdAcceso IS NULL
            UPDATE dbo.Usuarios SET IdPerfil = @IdPerfil, FechaUpd = GETDATE()
            WHERE IdUsuario = @IdUsuario;
        ELSE
            UPDATE dbo.Usuarios SET IdPerfil = @IdPerfil, IdAcceso = @IdAcceso, FechaUpd = GETDATE()
            WHERE IdUsuario = @IdUsuario;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        UpdUsuarioActivoAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Activa o desactiva (lógico) un usuario. Actualiza FechaUpd.
    Parámetros:    @IdUsuario BIGINT, @Activo BIT
    Retorno:       (sin result set) — el servicio devuelve True/False según commit.
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.UpdUsuarioActivoAdminDAsp
    @IdUsuario BIGINT,
    @Activo    BIT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        UPDATE dbo.Usuarios SET Activo = @Activo, FechaUpd = GETDATE()
        WHERE IdUsuario = @IdUsuario;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

-- ── Verificación (opcional, solo lectura) ────────────────────────
PRINT '016: SPs de escritura de usuarios creados/actualizados.';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name IN ('AddOrUpdUsuarioAdminDAsp','UpdUsuarioPerfilAccesoAdminDAsp','UpdUsuarioActivoAdminDAsp')
ORDER BY name;
GO
