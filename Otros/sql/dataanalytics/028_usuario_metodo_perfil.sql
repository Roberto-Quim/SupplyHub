-- Asignaciones independientes: dbo.Usuarios mantiene IdUsuario, IdAcceso e IdPerfil.
-- Ejecutar antes de desplegar el código nuevo. No borra ni duplica usuarios,
-- plantas, accesos históricos ni dbo.PerfilAccesos (027, ahora obsoleto).
USE DataAnalytics;
GO

/*
Nombre: GetValidaUsuarioMetodoDAsp
Creador: Roberto Yeshua Moreno Pedraza
Fecha: 2026-09-29
Parámetros: @IdAcceso INT (1 Google/correo, 2 AD, 3 nómina),
            @NoNomina NVARCHAR(20) opcional, @Correo NVARCHAR(255) opcional.
Retorno: Una fila (IdUsuario, IdPerfil); (0,0) si no hay una única asignación
         activa con perfil y método activos. No modifica datos.
Módulo: Autenticación / Autorización DataAnalytics.
*/
CREATE OR ALTER PROCEDURE dbo.GetValidaUsuarioMetodoDAsp
    @IdAcceso INT,
    @NoNomina NVARCHAR(20) = NULL,
    @Correo NVARCHAR(255) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @NoNomina = NULLIF(LTRIM(RTRIM(@NoNomina)), '');
    SET @Correo = NULLIF(LOWER(LTRIM(RTRIM(@Correo))), '');
    -- Contar también filas inactivas: la ambigüedad nunca escoge TOP 1.
    SELECT
      CASE WHEN COUNT(*) = 1 AND MAX(CONVERT(INT,u.Activo)) = 1
             AND MAX(CONVERT(INT,p.Activo)) = 1 AND MAX(CONVERT(INT,a.Activo)) = 1
           THEN MAX(u.IdUsuario) ELSE 0 END AS IdUsuario,
      CASE WHEN COUNT(*) = 1 AND MAX(CONVERT(INT,u.Activo)) = 1
             AND MAX(CONVERT(INT,p.Activo)) = 1 AND MAX(CONVERT(INT,a.Activo)) = 1
           THEN MAX(u.IdPerfil) ELSE 0 END AS IdPerfil
    FROM dbo.Usuarios u
    LEFT JOIN dbo.Perfiles p ON p.IdPerfil = u.IdPerfil
    LEFT JOIN dbo.Acceso a ON a.IdAcceso = u.IdAcceso
    WHERE u.IdAcceso = @IdAcceso AND (
        (@IdAcceso = 1 AND @Correo IS NOT NULL AND LOWER(LTRIM(RTRIM(u.Correo))) = @Correo)
        OR (@IdAcceso = 3 AND @NoNomina IS NOT NULL AND LTRIM(RTRIM(u.NoNomina)) = @NoNomina)
        OR (@IdAcceso = 2 AND (
            (@NoNomina IS NOT NULL AND LTRIM(RTRIM(u.NoNomina)) = @NoNomina)
            OR (@Correo IS NOT NULL AND LOWER(LTRIM(RTRIM(u.Correo))) = @Correo)
        ))
    );
END;
GO

/*
Nombre: GuardarUsuarioMetodoAdminDAsp
Creador: Roberto Yeshua Moreno Pedraza
Fecha: 2026-09-29
Parámetros: @IdUsuario BIGINT NULL para alta o ID para edición;
            @NoNomina NVARCHAR(20), @Correo NVARCHAR(255),
            @IdPerfil INT, @IdAcceso INT, @ActorIdPerfil INT.
Retorno: Una fila IdUsuario en éxito; THROW ante duplicados, datos o permisos
         inválidos. El llamador confirma/revierte la transacción.
Módulo: Administración / Usuarios / Asignaciones de ingreso.
*/
CREATE OR ALTER PROCEDURE dbo.GuardarUsuarioMetodoAdminDAsp
    @IdUsuario BIGINT,
    @NoNomina NVARCHAR(20),
    @Correo NVARCHAR(255),
    @IdPerfil INT,
    @IdAcceso INT,
    @ActorIdPerfil INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    IF @@TRANCOUNT = 0 THROW 51010, 'Se requiere transacción del llamador.', 1;

    -- Serializa altas/ediciones administrativas incluso en instalaciones sin
    -- índices compuestos. No se modifican restricciones existentes a ciegas.
    DECLARE @Filas BIGINT;
    SELECT @Filas = COUNT_BIG(*) FROM dbo.Usuarios WITH (TABLOCKX, HOLDLOCK);

    DECLARE @Actor NVARCHAR(100), @Destino NVARCHAR(100), @Actual NVARCHAR(100);
    SELECT @Actor = LOWER(LTRIM(RTRIM(Perfil))) FROM dbo.Perfiles
      WHERE IdPerfil = @ActorIdPerfil AND Activo = 1;
    SELECT @Destino = LOWER(LTRIM(RTRIM(Perfil))) FROM dbo.Perfiles
      WHERE IdPerfil = @IdPerfil AND Activo = 1;
    IF @Actor IS NULL OR @Actor NOT IN ('ti','administrador','admin') OR @Destino IS NULL
        THROW 51011, 'Perfil o actor no autorizado.', 1;
    IF @Actor <> 'ti' AND @Destino = 'ti'
        THROW 51011, 'Solo TI puede asignar el perfil TI.', 1;

    IF @IdUsuario IS NOT NULL
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM dbo.Usuarios WHERE IdUsuario = @IdUsuario)
            THROW 51013, 'Asignación inexistente.', 1;
        -- En edición los identificadores se leen del registro, no del formulario.
        SELECT @NoNomina = u.NoNomina, @Correo = u.Correo,
               @Actual = LOWER(LTRIM(RTRIM(p.Perfil)))
          FROM dbo.Usuarios u LEFT JOIN dbo.Perfiles p ON p.IdPerfil = u.IdPerfil
          WHERE u.IdUsuario = @IdUsuario;
        IF @Actor <> 'ti' AND (@Actual IS NULL OR @Actual = 'ti')
            THROW 51011, 'Solo TI puede editar esta asignación.', 1;
    END;
    SET @NoNomina = NULLIF(LTRIM(RTRIM(@NoNomina)), '');
    SET @Correo = NULLIF(LOWER(LTRIM(RTRIM(@Correo))), '');
    IF @IdAcceso IS NULL OR @IdAcceso NOT IN (1,2,3)
       OR (@IdAcceso = 1 AND @Correo IS NULL)
       OR (@IdAcceso = 3 AND @NoNomina IS NULL)
       OR (@IdAcceso = 2 AND @NoNomina IS NULL AND @Correo IS NULL)
       OR LEN(@NoNomina) > 10 OR LEN(@Correo) > 200
        THROW 51014, 'Identidad o método inválidos.', 1;
    IF NOT EXISTS (SELECT 1 FROM dbo.Acceso WHERE IdAcceso = @IdAcceso AND Activo = 1)
        THROW 51014, 'Método no disponible.', 1;

    IF EXISTS (SELECT 1 FROM dbo.Usuarios u
        WHERE u.IdAcceso = @IdAcceso
          AND (@IdUsuario IS NULL OR u.IdUsuario <> @IdUsuario)
          AND ((@NoNomina IS NOT NULL AND LTRIM(RTRIM(u.NoNomina)) = @NoNomina)
               OR (@Correo IS NOT NULL AND LOWER(LTRIM(RTRIM(u.Correo))) = @Correo)))
        THROW 51012, 'Ya existe una asignación para esta persona y método.', 1;

    IF @IdUsuario IS NULL
    BEGIN
        INSERT INTO dbo.Usuarios (NoNomina, Correo, IdPerfil, IdAcceso, Activo, FechaAdd, FechaUpd)
        VALUES (@NoNomina, @Correo, @IdPerfil, @IdAcceso, 1, GETDATE(), GETDATE());
        SET @IdUsuario = CONVERT(BIGINT, SCOPE_IDENTITY());
    END
    ELSE
        UPDATE dbo.Usuarios SET IdPerfil = @IdPerfil, IdAcceso = @IdAcceso, FechaUpd = GETDATE()
          WHERE IdUsuario = @IdUsuario;
    SELECT @IdUsuario AS IdUsuario;
END;
GO

-- Verificación de objetos. La cuenta de aplicación necesita EXECUTE en ambos SP.
SELECT name, modify_date FROM sys.procedures
WHERE schema_id = SCHEMA_ID('dbo')
  AND name IN ('GetValidaUsuarioMetodoDAsp', 'GuardarUsuarioMetodoAdminDAsp')
ORDER BY name;

-- Duplicados que deben revisarse antes de probar accesos. No se corrigen ni borran.
SELECT IdAcceso, LTRIM(RTRIM(NoNomina)) AS NoNomina, COUNT(*) AS Asignaciones
FROM dbo.Usuarios WHERE NULLIF(LTRIM(RTRIM(NoNomina)), '') IS NOT NULL
GROUP BY IdAcceso, LTRIM(RTRIM(NoNomina)) HAVING COUNT(*) > 1;
SELECT IdAcceso, LOWER(LTRIM(RTRIM(Correo))) AS Correo, COUNT(*) AS Asignaciones
FROM dbo.Usuarios WHERE NULLIF(LTRIM(RTRIM(Correo)), '') IS NOT NULL
GROUP BY IdAcceso, LOWER(LTRIM(RTRIM(Correo))) HAVING COUNT(*) > 1;

-- Revisar índices únicos: uno solo por NoNomina o Correo impediría varios métodos.
-- No eliminar índices/constraints sin revisar sus columnas y dependencias.
SELECT i.name, i.is_unique_constraint, c.name AS Columna, ic.key_ordinal, i.filter_definition
FROM sys.indexes i JOIN sys.index_columns ic
  ON ic.object_id = i.object_id AND ic.index_id = i.index_id
JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
WHERE i.object_id = OBJECT_ID('dbo.Usuarios') AND i.is_unique = 1 AND ic.key_ordinal > 0
ORDER BY i.name, ic.key_ordinal;
GO
