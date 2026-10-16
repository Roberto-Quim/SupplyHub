-- =============================================================
-- 015_create_sp_user_admin_reads.sql
-- Procedimientos almacenOados de LECTURA de Administración de Usuarios (fase 4A).
--
-- Crea (idempotente, CREATE OR ALTER) SOLO lecturas:
--   dbo.GetUsuariosAdminDAsp     → listado de usuarios (reemplaza list_users).
--   dbo.GetUsuarioAdminByIdDAsp  → un usuario por IdUsuario (get_user_by_id).
--   dbo.GetUsuarioPerfilIdDAsp   → IdPerfil de un usuario (get_user_profile_id).
--   dbo.GetPerfilNombreDAsp      → nombre de un perfil (get_profile_name).
--   dbo.GetPerfilesCatalogoDAsp  → catálogo de perfiles activos (list_profiles).
--   dbo.GetAccesosCatalogoDAsp   → catálogo de accesos activos (list_acceso).
--
-- IMPORTANTE: las columnas y el ORDEN de GetUsuariosAdminDAsp / GetUsuarioAdminByIdDAsp
-- DEBEN coincidir EXACTAMENTE con el SELECT directo del servicio (_row_to_user las
-- mapea por posición):
--   IdUsuario, NoNomina, Correo, IdPerfil, Perfil, Activo, FechaAdd, FechaUpd, IdAcceso, Acceso
-- (El esquema NO tiene columna Nombre; no se inventa.)
--
-- Esta fase NO migra escrituras (upsert_user, update_user_profile, set_user_active).
-- El script NO cambia datos ni crea tablas: solo crea/actualiza procedimientos.
--
-- ORDEN DE EJECUCIÓN EN BD:
--   1. Tablas base de Usuarios/Perfiles/Acceso (ya existentes en la BD).
--   2. 015_create_sp_user_admin_reads.sql (este archivo).
--
-- ⚠️  NO EJECUTAR SIN AUTORIZACIÓN del Ing./DBA. Este archivo solo versiona el DDL.
-- =============================================================

USE DataAnalytics;
GO

/*
    Nombre:        GetUsuariosAdminDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Lista todos los usuarios con su perfil y acceso, más recientes
                   primero (ORDER BY IdUsuario DESC). LEFT JOIN para no descartar
                   filas con IdPerfil/IdAcceso NULL.
    Parámetros:    (ninguno)
    Retorno:       IdUsuario, NoNomina, Correo, IdPerfil, Perfil, Activo, FechaAdd,
                   FechaUpd, IdAcceso, Acceso.
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.GetUsuariosAdminDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT u.IdUsuario, u.NoNomina, u.Correo, u.IdPerfil, p.Perfil,
               u.Activo, u.FechaAdd, u.FechaUpd,
               u.IdAcceso, ac.Acceso
        FROM dbo.Usuarios u
        LEFT JOIN dbo.Perfiles p ON u.IdPerfil = p.IdPerfil
        LEFT JOIN dbo.Acceso  ac ON ac.IdAcceso = u.IdAcceso
        ORDER BY u.IdUsuario DESC;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetUsuarioAdminByIdDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Devuelve un usuario por IdUsuario con su perfil y acceso.
    Parámetros:    @IdUsuario BIGINT
    Retorno:       Misma forma/columnas que GetUsuariosAdminDAsp (0 o 1 fila).
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.GetUsuarioAdminByIdDAsp
    @IdUsuario BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT u.IdUsuario, u.NoNomina, u.Correo, u.IdPerfil, p.Perfil,
               u.Activo, u.FechaAdd, u.FechaUpd,
               u.IdAcceso, ac.Acceso
        FROM dbo.Usuarios u
        LEFT JOIN dbo.Perfiles p ON u.IdPerfil = p.IdPerfil
        LEFT JOIN dbo.Acceso  ac ON ac.IdAcceso = u.IdAcceso
        WHERE u.IdUsuario = @IdUsuario;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetUsuarioPerfilIdDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Devuelve el IdPerfil actual de un usuario (para la jerarquía
                   TI/Administrador). Resuelve el perfil desde la BD, no del POST.
    Parámetros:    @IdUsuario BIGINT
    Retorno:       IdPerfil (0 o 1 fila).
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.GetUsuarioPerfilIdDAsp
    @IdUsuario BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT IdPerfil FROM dbo.Usuarios WHERE IdUsuario = @IdUsuario;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetPerfilNombreDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Devuelve el nombre del perfil para un IdPerfil.
    Parámetros:    @IdPerfil BIGINT
    Retorno:       Perfil (0 o 1 fila).
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.GetPerfilNombreDAsp
    @IdPerfil BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT Perfil FROM dbo.Perfiles WHERE IdPerfil = @IdPerfil;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetPerfilesCatalogoDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Catálogo de perfiles ACTIVOS para el dropdown de usuarios.
    Parámetros:    (ninguno)
    Retorno:       IdPerfil, Perfil (ORDER BY Perfil).
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.GetPerfilesCatalogoDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT IdPerfil, Perfil FROM dbo.Perfiles WHERE Activo = 1 ORDER BY Perfil;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetAccesosCatalogoDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-06-30
    Descripción:   Catálogo de tipos de acceso ACTIVOS para el dropdown de usuarios.
    Parámetros:    (ninguno)
    Retorno:       IdAcceso, Acceso (ORDER BY IdAcceso).
    Módulo:        Administración / Usuarios
*/
CREATE OR ALTER PROCEDURE dbo.GetAccesosCatalogoDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT IdAcceso, Acceso FROM dbo.Acceso WHERE Activo = 1 ORDER BY IdAcceso;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

-- ── Verificación (opcional, solo lectura) ────────────────────────
PRINT '015: SPs de lectura de usuarios creados/actualizados.';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name IN ('GetUsuariosAdminDAsp','GetUsuarioAdminByIdDAsp','GetUsuarioPerfilIdDAsp',
               'GetPerfilNombreDAsp','GetPerfilesCatalogoDAsp','GetAccesosCatalogoDAsp')
ORDER BY name;
GO
