# Script para iniciar el cliente
# Uso: .\start_client.ps1 <usuario> <sala> [host:puerto]
param(
    [Parameter(Mandatory=$true)]
    [string]$Usuario,
    
    [Parameter(Mandatory=$true)]
    [string]$Sala,
    
    [Parameter(Mandatory=$false)]
    [string]$Host = "localhost:50051"
)

$env:PYTHONPATH = "$PSScriptRoot"
python client/client.py $Usuario $Sala $Host

