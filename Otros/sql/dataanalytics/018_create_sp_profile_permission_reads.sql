-- =============================================================
-- 018_create_sp_profile_permission_reads.sql
-- Procedimientos almacenados de LECTURA de Perfiles / Permisos / Módulos / Menú (fase 6).
--
-- Crea (idempotente, CREATE OR ALTER) SOLO lecturas. NINGUNA escritura, NINGUNA tabla,
-- NINGÚN cambio de datos: solo SELECTs. La jerarquía (TI/Administrador/Usuario), las
-- rutas y los nombres del menú NO cambian: estos SPs devuelven exactamente las mismas
-- columnas/orden que las queries directas que reemplazan (los servicios mapean por
-- posición, así que el orden de columnas es contractual).
--
--   Permisos / Menú (dataanalytics_permissions_service.py):
--     dbo.GetSubmodulosPermitidosEstadoDAsp @IdPerfil → get_submodulos_permitidos_estado
--     dbo.GetMenuJerarquicoDAsp             @IdPerfil → get_menu_jerarquico
--   Perfiles (dataanalytics_perfiles_service.py):
--     dbo.GetPerfilesAdminReadDAsp                    → list_profiles_full
--     dbo.GetPerfilByIdReadDAsp             @IdPerfil → get_profile_with_submodulos (perfil)
--     dbo.GetPerfilSubmodulosDAsp           @IdPerfil → get_profile_with_submodulos (asignaciones)
--     dbo.GetSubmodulosAsignablesReadDAsp             → list_all_submodulos_for_assignment
--   Módulos / Submódulos (dataanalytics_modulos_service.py):
--     dbo.GetModulosAdminReadDAsp        @SoloActivos → list_modulos
--     dbo.GetModuloByIdReadDAsp             @IdModulo → get_modulo
--     dbo.GetSubmodulosAdminReadDAsp @IdModulo,@SoloActivos → list_submodulos
--     dbo.GetSubmoduloByIdReadDAsp       @IdSubModulo → get_submodulo
--
-- NOTA: el chequeo de esquema (INFORMATION_SCHEMA) y el fallback legacy por ClaveModulo
-- (_get_modulos_permitidos_legacy) NO se migran: el primero es introspección de meta-datos
-- y el segundo es la propia red de seguridad de compatibilidad. Las ESCRITURAS de perfiles
-- y módulos NO se tocan en esta fase.
--
-- ORDEN DE EJECUCIÓN EN BD:
--   1. Tablas base (Perfiles, Modulos, Submodulo, PerfilModulos) ya migradas (007+).
--   2. 018_create_sp_profile_permission_reads.sql (este archivo).
--
-- ⚠️  NO EJECUTAR SIN AUTORIZACIÓN del Ing./DBA. Este archivo solo versiona el DDL.
-- =============================================================

USE DataAnalytics;
GO

/*
    Nombre:        GetSubmodulosPermitidosEstadoDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Rutas de submódulos que un perfil puede ver (modelo jerárquico):
                   PerfilModulos → Submodulo → Modulos → Perfiles, todos Activo=1.
                   El servicio ya validó que el esquema jerárquico existe antes de llamar.
    Parámetros:    @IdPerfil BIGINT
    Retorno:       Ruta (0..N filas).
    Módulo:        Administración / Permisos
*/
CREATE OR ALTER PROCEDURE dbo.GetSubmodulosPermitidosEstadoDAsp
    @IdPerfil BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT s.Ruta
        FROM dbo.PerfilModulos pm
        INNER JOIN dbo.Submodulo s ON s.IdSubModulo = pm.IdSubModulo
        INNER JOIN dbo.Modulos   m ON m.IdModulo    = s.IdModulo
        INNER JOIN dbo.Perfiles  p ON p.IdPerfil    = pm.IdPerfil
        WHERE pm.IdPerfil = @IdPerfil
          AND pm.Activo   = 1
          AND s.Activo    = 1
          AND m.Activo    = 1
          AND p.Activo    = 1;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetMenuJerarquicoDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Filas módulo→submódulo permitidas para construir el menú jerárquico
                   del perfil. El servicio agrupa por módulo. Orden por m.Orden, s.Orden.
    Parámetros:    @IdPerfil BIGINT
    Retorno:       IdModulo, Modulo, Orden, IdSubModulo, SubModulo, Ruta, SubOrden.
    Módulo:        Administración / Permisos
*/
CREATE OR ALTER PROCEDURE dbo.GetMenuJerarquicoDAsp
    @IdPerfil BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT m.IdModulo, COALESCE(m.Modulo, '') AS Modulo, m.Orden,
               s.IdSubModulo, s.SubModulo, s.Ruta, s.Orden AS SubOrden
        FROM dbo.Modulos m
        INNER JOIN dbo.Submodulo s
               ON  s.IdModulo  = m.IdModulo
               AND s.Activo    = 1
        INNER JOIN dbo.PerfilModulos pm
               ON  pm.IdSubModulo = s.IdSubModulo
               AND pm.IdPerfil    = @IdPerfil
               AND pm.Activo      = 1
        INNER JOIN dbo.Perfiles p
               ON  p.IdPerfil = pm.IdPerfil
               AND p.Activo   = 1
        WHERE  m.Activo = 1
        ORDER BY m.Orden, s.Orden;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetPerfilesAdminReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Lista de perfiles (activos e inactivos) con su conteo de submódulos
                   asignados activos, para la pantalla de administración de perfiles.
    Parámetros:    (ninguno)
    Retorno:       IdPerfil, Perfil, Activo, FechaAdd, FechaUpd, NumSubmodulos.
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.GetPerfilesAdminReadDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT p.IdPerfil, p.Perfil, p.Activo, p.FechaAdd, p.FechaUpd,
               COUNT(pm.IdPerfilModulo) AS NumSubmodulos
        FROM dbo.Perfiles p
        LEFT JOIN dbo.PerfilModulos pm
               ON pm.IdPerfil = p.IdPerfil AND pm.Activo = 1
        GROUP BY p.IdPerfil, p.Perfil, p.Activo, p.FechaAdd, p.FechaUpd
        ORDER BY p.Perfil;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetPerfilByIdReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Datos base de un perfil por IdPerfil (para su pantalla de edición).
    Parámetros:    @IdPerfil BIGINT
    Retorno:       IdPerfil, Perfil, Activo, FechaAdd, FechaUpd (0 o 1 fila).
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.GetPerfilByIdReadDAsp
    @IdPerfil BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT IdPerfil, Perfil, Activo, FechaAdd, FechaUpd
        FROM dbo.Perfiles WHERE IdPerfil = @IdPerfil;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetPerfilSubmodulosDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Asignaciones (activas e inactivas) de un perfil: submódulo, ruta,
                   módulo y estado. Ordenadas por m.Orden, s.Orden.
    Parámetros:    @IdPerfil BIGINT
    Retorno:       IdSubModulo, SubModulo, Ruta, Modulo, Activo.
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.GetPerfilSubmodulosDAsp
    @IdPerfil BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT pm.IdSubModulo, s.SubModulo, s.Ruta,
               m.Modulo, pm.Activo
        FROM dbo.PerfilModulos pm
        INNER JOIN dbo.Submodulo s ON s.IdSubModulo = pm.IdSubModulo
        INNER JOIN dbo.Modulos   m ON m.IdModulo    = s.IdModulo
        WHERE pm.IdPerfil = @IdPerfil
        ORDER BY m.Orden, s.Orden;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetSubmodulosAsignablesReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Submódulos ACTIVOS (con su módulo activo) para el formulario de
                   asignación de perfiles. El servicio los agrupa por módulo.
    Parámetros:    (ninguno)
    Retorno:       IdSubModulo, SubModulo, Ruta, Orden, Activo, IdModulo, Modulo, ModuloOrden.
    Módulo:        Administración / Perfiles
*/
CREATE OR ALTER PROCEDURE dbo.GetSubmodulosAsignablesReadDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT s.IdSubModulo, s.SubModulo, s.Ruta, s.Orden, s.Activo,
               m.IdModulo, COALESCE(m.Modulo, '') AS Modulo, m.Orden AS ModuloOrden
        FROM dbo.Submodulo s
        INNER JOIN dbo.Modulos m ON m.IdModulo = s.IdModulo
        WHERE s.Activo = 1 AND m.Activo = 1
        ORDER BY m.Orden, s.Orden;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetModulosAdminReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Lista de módulos con su conteo de submódulos activos, ordenados por
                   Orden. Si @SoloActivos=1 filtra solo módulos activos.
    Parámetros:    @SoloActivos BIT = 0
    Retorno:       IdModulo, Modulo, Ruta, Orden, Activo, FechaAdd, FechaUpd, NumSubmodulos.
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.GetModulosAdminReadDAsp
    @SoloActivos BIT = 0
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT m.IdModulo, COALESCE(m.Modulo, '') AS Modulo,
               m.Ruta, m.Orden, m.Activo, m.FechaAdd, m.FechaUpd,
               COUNT(s.IdSubModulo) AS NumSubmodulos
        FROM dbo.Modulos m
        LEFT JOIN dbo.Submodulo s ON s.IdModulo = m.IdModulo AND s.Activo = 1
        WHERE (@SoloActivos = 0 OR m.Activo = 1)
        GROUP BY m.IdModulo, m.Modulo, m.Ruta, m.Orden, m.Activo,
                 m.FechaAdd, m.FechaUpd
        ORDER BY m.Orden, m.IdModulo;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetModuloByIdReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Datos de un módulo por IdModulo (para su pantalla de edición).
    Parámetros:    @IdModulo BIGINT
    Retorno:       IdModulo, Modulo, Ruta, Orden, Activo, FechaAdd, FechaUpd (0 o 1 fila).
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.GetModuloByIdReadDAsp
    @IdModulo BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT IdModulo, COALESCE(Modulo, '') AS Modulo,
               Ruta, Orden, Activo, FechaAdd, FechaUpd
        FROM dbo.Modulos WHERE IdModulo = @IdModulo;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetSubmodulosAdminReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Submódulos con el nombre de su módulo padre. Opcionalmente filtra por
                   módulo (@IdModulo) y/o solo activos (@SoloActivos). Orden por
                   m.Orden, s.Orden, s.IdSubModulo.
    Parámetros:    @IdModulo BIGINT = NULL, @SoloActivos BIT = 0
    Retorno:       IdSubModulo, IdModulo, SubModulo, Ruta, Orden, Activo, FechaAdd,
                   FechaUpd, Modulo.
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.GetSubmodulosAdminReadDAsp
    @IdModulo    BIGINT = NULL,
    @SoloActivos BIT    = 0
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT s.IdSubModulo, s.IdModulo, s.SubModulo, s.Ruta, s.Orden,
               s.Activo, s.FechaAdd, s.FechaUpd,
               COALESCE(m.Modulo, '') AS Modulo
        FROM dbo.Submodulo s
        INNER JOIN dbo.Modulos m ON m.IdModulo = s.IdModulo
        WHERE (@IdModulo IS NULL OR s.IdModulo = @IdModulo)
          AND (@SoloActivos = 0 OR s.Activo = 1)
        ORDER BY m.Orden, s.Orden, s.IdSubModulo;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetSubmoduloByIdReadDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-02
    Descripción:   Datos de un submódulo por IdSubModulo, con el nombre del módulo padre.
    Parámetros:    @IdSubModulo BIGINT
    Retorno:       IdSubModulo, IdModulo, SubModulo, Ruta, Orden, Activo, FechaAdd,
                   FechaUpd, Modulo (0 o 1 fila).
    Módulo:        Administración / Módulos
*/
CREATE OR ALTER PROCEDURE dbo.GetSubmoduloByIdReadDAsp
    @IdSubModulo BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT s.IdSubModulo, s.IdModulo, s.SubModulo, s.Ruta, s.Orden,
               s.Activo, s.FechaAdd, s.FechaUpd,
               COALESCE(m.Modulo, '') AS Modulo
        FROM dbo.Submodulo s
        INNER JOIN dbo.Modulos m ON m.IdModulo = s.IdModulo
        WHERE s.IdSubModulo = @IdSubModulo;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

-- ── Verificación (opcional, solo lectura) ────────────────────────
PRINT '018: SPs de lectura de Perfiles/Permisos/Módulos/Menú creados/actualizados.';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name IN ('GetSubmodulosPermitidosEstadoDAsp','GetMenuJerarquicoDAsp',
               'GetPerfilesAdminReadDAsp','GetPerfilByIdReadDAsp','GetPerfilSubmodulosDAsp',
               'GetSubmodulosAsignablesReadDAsp','GetModulosAdminReadDAsp','GetModuloByIdReadDAsp',
               'GetSubmodulosAdminReadDAsp','GetSubmoduloByIdReadDAsp')
ORDER BY name;
GO
