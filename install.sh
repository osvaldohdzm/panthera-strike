#!/bin/bash

# Asegurar que el script se ejecute como root
if [ "$(id -u)" -ne 0 ]; then
  echo "Este script debe ejecutarse como root o con sudo."
  exit 1
fi

echo "=================================================="
echo "Iniciando script de instalación de Kali Linux..."
echo "=================================================="
echo "FECHA Y HORA ACTUAL: $(date)"
echo "=================================================="

# Establecer DEBIAN_FRONTEND en noninteractive para evitar prompts
export DEBIAN_FRONTEND=noninteractive

echo "=================================================="
echo "Actualizando e instalando actualizaciones del sistema..."
echo "=================================================="
if ! apt update -y && apt upgrade -y; then
  echo "ADVERTENCIA: Error al actualizar el sistema. La instalación podría no completarse correctamente."
fi

echo "=================================================="
echo "Instalando y habilitando SSH (openssh-server)..."
echo "=================================================="
if ! apt install -y openssh-server; then
  echo "ADVERTENCIA: No se pudo instalar openssh-server."
else
  echo "SSH instalado. Habilitando servicio..."
  systemctl enable ssh
  systemctl start ssh
  if systemctl is-active --quiet ssh; then
    echo "SSH está activo."
  else
    echo "ADVERTENCIA: SSH no se pudo iniciar correctamente."
  fi
fi


apt install git

ip -a addr
