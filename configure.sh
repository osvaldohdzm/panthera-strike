#!/bin/bash

echo "🔧 Configurando sistema para máximo rendimiento y evitar suspensión..."

# Función para arreglar dpkg si está interrumpido
arreglar_dpkg_si_es_necesario() {
    if sudo fgrep -q "dpkg was interrupted" /var/log/dpkg.log 2>/dev/null || sudo test -f /var/lib/dpkg/lock; then
        echo "⚠️  Se detectó una interrupción de dpkg. Ejecutando 'dpkg --configure -a'..."
        sudo dpkg --configure -a
    fi
}

# Función para instalar un paquete si no está instalado
instalar_si_falta() {
    local paquete=$1
    local intentos=6
    local lockfile="/var/lib/dpkg/lock-frontend"

    # Esperar a que se libere el lock
    while sudo fuser "$lockfile" >/dev/null 2>&1; do
        echo "⏳ Esperando que se libere APT... ($intentos segundos restantes)"
        sleep 1
        intentos=$((intentos - 1))
        if [ "$intentos" -le 0 ]; then
            echo "⚠️  Tiempo de espera agotado. Eliminando proceso que bloquea APT..."
            pid=$(sudo fuser "$lockfile" 2>/dev/null | awk '{print $1}')
            if [ -n "$pid" ]; then
                echo "🔪 Matando proceso PID $pid que bloquea APT..."
                sudo kill -9 "$pid"
                sleep 2
            fi
            break
        fi
    done

    arreglar_dpkg_si_es_necesario

    if ! dpkg -s "$paquete" &> /dev/null; then
        echo "📦 Instalando $paquete..."
        sudo apt update && sudo apt install -y "$paquete" || {
            echo "⚠️  Reintentando instalación de $paquete después de configurar dpkg..."
            sudo dpkg --configure -a
            sudo apt install -y "$paquete"
        }
    else
        echo "✅ $paquete ya está instalado."
    fi
}

# 1. Prevenir suspensión al cerrar la tapa
echo "➡️  Configurando logind.conf para evitar suspensión al cerrar la tapa..."
sudo sed -i 's/^#*HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/^#*HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf

# Reiniciar systemd-logind
echo "🔄 Reiniciando systemd-logind..."
sudo systemctl restart systemd-logind

# 2. Desactivar suspensión automática
echo "➡️  Desactivando suspensión automática..."
instalar_si_falta "dconf-cli"
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' 2>/dev/null
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing' 2>/dev/null

# 3. Desactivar bloqueo automático y protector de pantalla
echo "➡️  Desactivando bloqueo automático y protector de pantalla..."
gsettings set org.gnome.desktop.screensaver lock-enabled false 2>/dev/null
gsettings set org.gnome.desktop.session idle-delay 0 2>/dev/null

# 4. Activar perfil de energía máximo rendimiento
echo "➡️  Configurando energía para máximo rendimiento..."
instalar_si_falta "power-profiles-daemon"
if command -v powerprofilesctl &> /dev/null; then
    sudo powerprofilesctl set performance
else
    echo "⚠️  'powerprofilesctl' no está disponible después de la instalación. Puede ser necesario reiniciar."
fi

echo "✅ Configuración completada. El equipo no se suspenderá, no se bloqueará y funcionará al máximo rendimiento."

