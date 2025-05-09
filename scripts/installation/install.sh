#!/bin/bash

# Verificar que se ejecuta como root
if [ "$(id -u)" -ne 0 ]; then
  echo "Este script debe ejecutarse como root o con sudo."
  exit 1
fi

echo "=================================================="
echo " INICIO DE INSTALACIÓN DE KALI LINUX - TODO INCLUIDO"
echo " FECHA Y HORA: $(date)"
echo "=================================================="

# Evitar prompts durante la instalación
export DEBIAN_FRONTEND=noninteractive

# Actualizar el sistema
echo ">> Actualizando el sistema..."
apt update -y && apt full-upgrade -y || {
  echo "ERROR: Falló la actualización del sistema."
  exit 1
}

# Instalar metapaquete de herramientas completas de Kali
echo ">> Instalando metapaquete: kali-linux-everything"
apt install -y kali-linux-everything || {
  echo "ERROR: No se pudo instalar el metapaquete."
}

# Instalar y habilitar SSH
echo ">> Instalando y habilitando SSH..."
apt install -y openssh-server
systemctl enable --now ssh

if systemctl is-active --quiet ssh; then
  echo "OK: Servicio SSH activo."
else
  echo "ERROR: SSH no se pudo iniciar correctamente."
fi

# Instalar herramientas básicas
echo ">> Instalando herramientas adicionales..."
apt install -y git curl net-tools lsb-release ca-certificates gnupg

# ==== INSTALACIÓN DE DOCKER (Método A → Método B) ====

echo ">> Instalando Docker (Método A: docker.io)..."
if apt install -y docker.io; then
  echo "OK: Docker.io instalado con éxito."
else
  echo "ERROR: Falló docker.io. Usando Método B: Docker CE desde repositorio oficial..."

  # Crear directorio de claves si no existe
  mkdir -p /etc/apt/keyrings

  # Importar clave GPG de Docker
  curl -fsSL https://download.docker.com/linux/debian/gpg | \
    gpg --dearmor -o /etc/apt/keyrings/docker.gpg

  # Usar "bookworm", versión base de Debian para Kali (ajustar si cambia)
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list

  # Instalar docker-ce
  apt update -y
  apt install -y docker-ce docker-ce-cli containerd.io || {
    echo "ERROR: Falló la instalación de Docker CE."
  }
fi

# Habilitar Docker y añadir usuario al grupo
echo ">> Habilitando Docker..."
systemctl enable --now docker
usermod -aG docker $SUDO_USER || usermod -aG docker $USER

# Probar Docker
echo ">> Ejecutando prueba de Docker..."
docker run hello-world || echo "NOTA: Puede requerirse cerrar sesión y volver a entrar para usar Docker sin sudo."




#!/bin/bash

# Variables
CAIDO_URL="https://caido.download/releases/v0.47.1/caido-cli-v0.47.1-linux-x86_64.tar.gz"
CAIDO_TAR="caido-cli-v0.47.1-linux-x86_64.tar.gz"
INSTALL_DIR="/usr/local/bin"

# Step 1: Download Caido CLI
echo "Downloading Caido CLI..."
wget -q $CAIDO_URL -O $CAIDO_TAR

# Step 2: Extract the tar.gz file
echo "Extracting the file..."
tar -xzvf $CAIDO_TAR

# Step 3: Move the executable to /usr/local/bin (make sure it's in the PATH)
echo "Moving Caido CLI to $INSTALL_DIR..."
sudo mv caido-cli $INSTALL_DIR

# Step 4: Set the executable permission
echo "Setting executable permission..."
sudo chmod +x $INSTALL_DIR/caido-cli

# Step 5: Verify installation
echo "Verifying the installation..."
if command -v caido-cli &> /dev/null; then
    echo "Caido CLI successfully installed!"
    caido-cli --version
else
    echo "Caido CLI installation failed!"
fi

# Clean up
echo "Cleaning up..."
rm -f $CAIDO_TAR

echo "Installation complete caido!"


    sudo apt install mitmproxy

# Mostrar IP actual
echo ">> Dirección IP actual:"
ip -4 addr show | grep inet | grep -v '127.0.0.1'


#!/bin/bash

# List of tools and their corresponding Debian package or installation command
declare -A tools=(
  ["amass"]="amass"
  ["subfinder"]="subfinder"
  ["dnsx"]="dnsx"
  ["naabu"]="naabu"
  ["nmap"]="nmap"
  ["httpx"]="httpx"
  ["whatweb"]="whatweb"
  ["nuclei"]="nuclei"
  ["nikto"]="nikto"
  ["wapiti"]="wapiti"
  ["ffuf"]="ffuf"
  ["dirsearch"]="git clone https://github.com/maurosoria/dirsearch.git"
  ["dirb"]="dirb"
  ["wpscan"]="wpscan"
  ["sqlmap"]="sqlmap"
)

echo "Checking for required tools..."

for tool in "${!tools[@]}"; do
  if ! command -v "$tool" &>/dev/null; then
    echo "[!] $tool not found."
    echo "Installing $tool..."
    if [[ "${tools[$tool]}" == git* ]]; then
      cd /opt || exit
      ${tools[$tool]}
      echo "Add /opt/$(basename "${tools[$tool]}" .git) to PATH if needed."
    else
      sudo apt-get install -y "${tools[$tool]}"
    fi
  else
    echo "[✔] $tool is already installed."
  fi
done

echo "All checks complete."


# Fin
echo "=================================================="
echo " FINALIZADO: El sistema está listo con herramientas de Kali y Docker."
echo "=================================================="

