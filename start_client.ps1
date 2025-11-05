# Script para iniciar el cliente
# Uso: .\start_client.ps1 <usuario> <sala> [servidor:puerto]
param(
    [Parameter(Mandatory=$true)]
    [string]$Usuario,
    
    [Parameter(Mandatory=$true)]
    [string]$Sala,
    
    [Parameter(Mandatory=$false)]
    [string]$Servidor = "localhost:50051"
)

$env:PYTHONPATH = "$PSScriptRoot"
python client/client.py $Usuario $Sala $Servidor

