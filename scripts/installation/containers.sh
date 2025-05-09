#!/bin/bash

# Puertos prohibidos por política interna
PROHIBITED_PORTS=(80 443 8080 8081 9090)

# Lista de puertos esenciales que deben estar libres
ESSENTIAL_PORTS=(3000 3443 7474 3780 49160 5001 8834)

# Función para verificar si un puerto está ocupado
check_port_host() {
    local port=$1
    if lsof -i:$port >/dev/null 2>&1; then
        echo "❌ ERROR: El puerto $port está en uso en la máquina host."
        return 1
    fi
    return 0
}

# Función para obtener todas las direcciones IP activas del sistema
get_all_ips() {
    ip addr show | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | grep -vE '^127|^::1'
}

# Función para lanzar un contenedor Docker
run_docker() {
    local image_name=$1
    local container_name=$2
    local container_port=$3
    local host_port=$4
    local extra_params=$5

    if [[ " ${PROHIBITED_PORTS[@]} " =~ " $host_port " ]]; then
        echo "❌ ERROR: El puerto $host_port está prohibido por política interna."
        return 1
    fi

    if ! check_port_host $host_port; then
        return 1
    fi

    echo "🔄 Descargando imagen: $image_name..."
    docker pull $image_name

    echo "🚀 Iniciando contenedor '$container_name' en puerto $host_port..."
    docker run -d -p $host_port:$container_port --name $container_name $extra_params $image_name

    echo "🌐 El contenedor '$container_name' está activo en las siguientes URLs:"
    for ip in $(get_all_ips); do
        echo "   ➤ http://$ip:$host_port"
    done
    echo "   ➤ http://127.0.0.1:$host_port"

    while true; do
        read -p "¿Deseas mantener el contenedor '$container_name' activo? (Y/N): " yn
        case $yn in
            [Yy]* )
                echo "✅ El contenedor '$container_name' continuará activo."
                break
                ;;
            [Nn]* )
                echo "⏹️ Deteniendo contenedor '$container_name'..."
                docker stop $container_name
                docker rm $container_name
                break
                ;;
            * ) echo "Por favor responde con Y o N.";;
        esac
    done
}

# Comprobación de puertos esenciales
echo "🔍 Verificando disponibilidad de puertos requeridos..."
for port in "${ESSENTIAL_PORTS[@]}"; do
    check_port_host $port || exit 1
done
echo "✅ Todos los puertos requeridos están libres."

# Mostrar IPs activas
echo "🌐 IPs activas del sistema:"
get_all_ips | sed 's/^/   ➤ /'

# Lanzamiento de contenedores
run_docker "lissy93/web-check" "web-check" "3000" "3000" ""
run_docker "vouu/acu14:latest" "awvs" "3443" "3443" ""
run_docker "belane/bloodhound" "bloodhound" "7474" "7474" "-e DISPLAY=unix$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix --device=/dev/dri:/dev/dri -v $(pwd)/bh-data:/data"
run_docker "vouu/nexpose:preview" "nexpose" "3780" "3780" ""
run_docker "whithajess/dockernexpose" "nexpose_container" "3780" "49160" ""
run_docker "mikesplain/openvas" "openvas" "443" "443" ""
run_docker "dtagdevsec/spiderfoot:24.04.1" "spiderfoot" "8080" "5001" ""
run_docker "ramisec/nessus" "nessus" "8834" "8834" ""

echo "✅ Todos los contenedores han sido gestionados correctamente."

