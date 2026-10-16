-- =============================================================
-- 017_create_sp_usuario_plantas.sql
-- Procedimientos almacenados de Plantas por usuario (fase 5).
--
-- Crea (idempotente, CREATE OR ALTER) lecturas y escrituras de Plantas:
--   dbo.GetPlantasDisponiblesDAsp      → catálogo de las 5 plantas (list_plantas_disponibles).
--   dbo.GetUsuarioPlantasDAsp          → plantas activas de un usuario (get_usuario_plantas).
--   dbo.GetUsuariosPlantasMapDAsp      → mapa IdUsuario→ClavePlanta activas (get_plantas_por_usuario_map).
--   dbo.SetUsuarioPlantasDAsp          → upsert lógico del set de plantas (set_usuario_plantas).
--   dbo.EnsureUsuarioPlantaInicialDAsp → asignación inicial si no tiene (ensure_usuario_planta_inicial).
--
-- REGLAS DE NEGOCIO CONSERVADAS (viven en Python y se replican aquí):
--   - El catálogo oficial vive en SingleSignOnMcx.dbo.PlantasMcx (nombre de 3 partes);
--     la asignación en DataAnalytics.dbo.UsuarioSitios (col. ClavePlanta).
--   - La UI/servicio hablan de "Plantas" aunque la tabla se llame UsuarioSitios.
--   - ALLOWLIST de 5 claves normales: BHK, FDM, QCT, MCM, TEN. Nunca se guardan
--     nombres completos ni 'MCX'/'RAMOS'/'TENANGO'. La normalización de 'MCX' por
--     descripción (RAMOS→MCM, TENANGO→TEN, en duda→MCM) y el fallback 'MCM' se
--     resuelven en Python ANTES de invocar SetUsuarioPlantasDAsp / EnsureUsuarioPlantaInicialDAsp,
--     que reciben SOLO claves ya validadas contra el allowlist.
--
-- PRINCIPIO DE SEGURIDAD: la AUTORIZACIÓN/JERARQUÍA (TI ve/asigna todas; Admin no
-- salta jerarquía; Usuario no asigna) y la VALIDACIÓN de claves permitidas viven en
-- Python (dataanalytics_usuario_plantas_service.py). Estos SPs SOLO ejecutan la
-- operación de datos ya autorizada. NO crean tablas ni cambian catálogos.
--
-- ORDEN DE EJECUCIÓN EN BD:
--   1. Tablas base (dbo.UsuarioSitios) y vista/tabla SingleSignOnMcx.dbo.PlantasMcx (existentes).
--   2. 017_create_sp_usuario_plantas.sql (este archivo).
--
-- ⚠️  NO EJECUTAR SIN AUTORIZACIÓN del Ing./DBA. Este archivo solo versiona el DDL.
-- =============================================================

USE DataAnalytics;
GO

/*
    Nombre:        GetPlantasDisponiblesDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-01
    Descripción:   Catálogo de plantas asignables: las 5 del allowlist, leídas de la
                   fuente oficial SingleSignOnMcx.dbo.PlantasMcx, ordenadas
                   BHK, FDM, QCT, MCM, TEN. Los nombres/datos visibles vienen de
                   PlantasMcx (no de constantes).
    Parámetros:    (ninguno)
    Retorno:       ClavePlanta, ClaveCompania, Planta, PlantaQuestum, ClavePlantaQues,
                   OrganizationCode, Domicilio, Telefono (mismo orden que el servicio).
    Módulo:        Administración / Plantas
*/
CREATE OR ALTER PROCEDURE dbo.GetPlantasDisponiblesDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT ClavePlanta, ClaveCompania, Planta, PlantaQuestum, ClavePlantaQues,
               OrganizationCode, Domicilio, Telefono
        FROM SingleSignOnMcx.dbo.PlantasMcx
        WHERE LTRIM(RTRIM(ClavePlanta)) IN ('BHK', 'FDM', 'MCM', 'QCT', 'TEN')
        ORDER BY CASE LTRIM(RTRIM(ClavePlanta))
                 WHEN 'BHK' THEN 1 WHEN 'FDM' THEN 2 WHEN 'QCT' THEN 3
                 WHEN 'MCM' THEN 4 WHEN 'TEN' THEN 5 ELSE 99 END;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetUsuarioPlantasDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-01
    Descripción:   Plantas ACTIVAS asignadas a un usuario en UsuarioSitios, limitadas
                   al allowlist de 5. El nombre se resuelve desde PlantasMcx (LEFT JOIN).
    Parámetros:    @IdUsuario BIGINT
    Retorno:       ClavePlanta, Planta, PlantaQuestum, ClavePlantaQues.
    Módulo:        Administración / Plantas
*/
CREATE OR ALTER PROCEDURE dbo.GetUsuarioPlantasDAsp
    @IdUsuario BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT LTRIM(RTRIM(us.ClavePlanta)) AS ClavePlanta, pm.Planta,
               pm.PlantaQuestum, pm.ClavePlantaQues
        FROM dbo.UsuarioSitios us
        LEFT JOIN SingleSignOnMcx.dbo.PlantasMcx pm
               ON LTRIM(RTRIM(pm.ClavePlanta)) = LTRIM(RTRIM(us.ClavePlanta))
        WHERE us.IdUsuario = @IdUsuario AND us.Activo = 1
          AND LTRIM(RTRIM(us.ClavePlanta)) IN ('BHK', 'FDM', 'MCM', 'QCT', 'TEN');
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        GetUsuariosPlantasMapDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-01
    Descripción:   Mapa de todas las plantas ACTIVAS por usuario (una sola consulta),
                   para precargar checkboxes en el listado. El filtrado al allowlist
                   se hace en el servicio (defensa en memoria).
    Parámetros:    (ninguno)
    Retorno:       IdUsuario, ClavePlanta.
    Módulo:        Administración / Plantas
*/
CREATE OR ALTER PROCEDURE dbo.GetUsuariosPlantasMapDAsp
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        SELECT IdUsuario, LTRIM(RTRIM(ClavePlanta)) AS ClavePlanta
        FROM dbo.UsuarioSitios
        WHERE Activo = 1;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        SetUsuarioPlantasDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-01
    Descripción:   Upsert LÓGICO del conjunto de plantas de un usuario (no borra físico):
                   desactiva las que ya no estén seleccionadas, reactiva las existentes
                   seleccionadas e inserta las nuevas. Recibe las claves ya normalizadas
                   y validadas por el servicio (allowlist) como CSV; aquí solo se
                   dividen con STRING_SPLIT. Si @ClavesCsv es NULL/'', desactiva todas.
    Parámetros:    @IdUsuario BIGINT, @ClavesCsv NVARCHAR(400) = NULL  (p. ej. 'BHK,MCM')
    Retorno:       (sin result set) — el servicio confirma con commit/rollback.
    Módulo:        Administración / Plantas
*/
CREATE OR ALTER PROCEDURE dbo.SetUsuarioPlantasDAsp
    @IdUsuario BIGINT,
    @ClavesCsv NVARCHAR(400) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        DECLARE @Claves TABLE (Clave NVARCHAR(20) PRIMARY KEY);
        INSERT INTO @Claves (Clave)
        SELECT DISTINCT LTRIM(RTRIM(value))
        FROM STRING_SPLIT(COALESCE(@ClavesCsv, ''), ',')
        WHERE LTRIM(RTRIM(value)) <> '';

        -- Desactivar las que ya no estén seleccionadas (todas si el set es vacío).
        UPDATE dbo.UsuarioSitios
        SET Activo = 0, FechaUpd = GETDATE()
        WHERE IdUsuario = @IdUsuario
          AND LTRIM(RTRIM(ClavePlanta)) NOT IN (SELECT Clave FROM @Claves);

        -- Reactivar las seleccionadas que ya existían.
        UPDATE us
        SET Activo = 1, FechaUpd = GETDATE()
        FROM dbo.UsuarioSitios us
        INNER JOIN @Claves c ON LTRIM(RTRIM(us.ClavePlanta)) = c.Clave
        WHERE us.IdUsuario = @IdUsuario;

        -- Insertar las seleccionadas que aún no existían.
        INSERT INTO dbo.UsuarioSitios (IdUsuario, ClavePlanta, Activo, FechaAdd, FechaUpd)
        SELECT @IdUsuario, c.Clave, 1, GETDATE(), GETDATE()
        FROM @Claves c
        WHERE NOT EXISTS (
            SELECT 1 FROM dbo.UsuarioSitios us
            WHERE us.IdUsuario = @IdUsuario
              AND LTRIM(RTRIM(us.ClavePlanta)) = c.Clave
        );
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

/*
    Nombre:        EnsureUsuarioPlantaInicialDAsp
    Creador:       Roberto Yeshua Moreno Pedraza
    Fecha:         2026-07-01
    Descripción:   Asignación AUTOMÁTICA de planta inicial al dar de alta un usuario.
                   Si el usuario YA tiene alguna planta activa → no hace nada. Si no,
                   reactiva la clave si existía (inactiva) o la inserta (Activo=1).
                   La clave llega ya derivada/validada por el servicio (una de las 5).
    Parámetros:    @IdUsuario BIGINT, @Clave NVARCHAR(20)
    Retorno:       Asignada BIT (1 = asignó/reactivó; 0 = el usuario ya tenía plantas).
    Módulo:        Administración / Plantas
*/
CREATE OR ALTER PROCEDURE dbo.EnsureUsuarioPlantaInicialDAsp
    @IdUsuario BIGINT,
    @Clave     NVARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        IF EXISTS (SELECT 1 FROM dbo.UsuarioSitios
                   WHERE IdUsuario = @IdUsuario AND Activo = 1)
        BEGIN
            SELECT CAST(0 AS BIT) AS Asignada;
            RETURN;
        END

        IF EXISTS (SELECT 1 FROM dbo.UsuarioSitios
                   WHERE IdUsuario = @IdUsuario AND LTRIM(RTRIM(ClavePlanta)) = @Clave)
            UPDATE dbo.UsuarioSitios SET Activo = 1, FechaUpd = GETDATE()
            WHERE IdUsuario = @IdUsuario AND LTRIM(RTRIM(ClavePlanta)) = @Clave;
        ELSE
            INSERT INTO dbo.UsuarioSitios (IdUsuario, ClavePlanta, Activo, FechaAdd, FechaUpd)
            VALUES (@IdUsuario, @Clave, 1, GETDATE(), GETDATE());

        SELECT CAST(1 AS BIT) AS Asignada;
    END TRY
    BEGIN CATCH
        DECLARE @M NVARCHAR(4000)=ERROR_MESSAGE(), @S INT=ERROR_SEVERITY(), @T INT=ERROR_STATE();
        RAISERROR(@M, @S, @T);
    END CATCH
END
GO

-- ── Verificación (opcional, solo lectura) ────────────────────────
PRINT '017: SPs de Plantas por usuario creados/actualizados.';
SELECT name, create_date, modify_date
FROM sys.procedures
WHERE name IN ('GetPlantasDisponiblesDAsp','GetUsuarioPlantasDAsp','GetUsuariosPlantasMapDAsp',
               'SetUsuarioPlantasDAsp','EnsureUsuarioPlantaInicialDAsp')
ORDER BY name;
GO
