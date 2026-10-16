# Configuración local cifrada

`local-test.env.fernet` contiene la configuración local de pruebas cifrada con Fernet (cifrado autenticado). La llave se transfiere por separado y nunca se publica en GitHub.

En Git Bash, desde la raíz del repositorio y con el entorno virtual activo:

```bash
python scripts/restore_local_env.py --key-file /c/ruta/segura/SupplyHub-feat8.5-env.key
```

Se crea `.env` únicamente si todavía no existe. Si ya tienes uno, conserva el anterior cambiándole el nombre antes de restaurar, o usa `--output .env.recuperado` para revisar la configuración primero.

La configuración es una copia de esta laptop, con integraciones y direcciones de prueba; no habilita accesos corporativos. Una actualización del `.env` local no actualiza automáticamente el archivo cifrado. No guardes la llave junto al archivo cifrado en el repositorio.
