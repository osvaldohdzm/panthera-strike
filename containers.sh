#!/bin/bash

# Función para comprobar si un puerto está en uso
check_port() {
    if lsof -i:$1 >/dev/null 2>&1; then
        echo "ERROR: El puerto $1 ya está en uso."
        return 1
    else
        return 0
    fi
}

# Función para iniciar el contenedor
run_docker() {
    local image_name=$1
    local container_name=$2
    local port_mapping=$3
    local extra_params=$4

    # Descargar la imagen Docker si no está presente
    echo "Descargando imagen: $image_name..."
    docker pull $image_name

    # Verificar si el contenedor ya está en ejecución
    if docker ps --filter "name=$container_name" --format "{{.Names}}" | grep -w $container_name; then
        echo "El contenedor '$container_name' ya está en ejecución."
    else
        # Iniciar el contenedor con los puertos y parámetros adicionales
        echo "Iniciando contenedor '$container_name' con mapeo de puertos $port_mapping..."
        docker run -d -p $port_mapping --name $container_name $extra_params $image_name
    fi
}

# Función para detener un contenedor
stop_docker() {
    local container_name=$1
    echo "Deteniendo contenedor '$container_name'..."
    docker stop $container_name
    docker rm $container_name
}

# Comprobación de puertos antes de ejecutar
check_port 3000 || exit 1
check_port 3443 || exit 1
check_port 7474 || exit 1
check_port 3780 || exit 1
check_port 49160 || exit 1
check_port 443 || exit 1
check_port 5001 || exit 1
check_port 8834 || exit 1



# Configuración de contenedores:
# Contenedor Web-Check (puerto 3000)
run_docker "lissy93/web-check" "web-check" "3000:3000" ""

# Contenedor AWVS (puerto 3443)
run_docker "vouu/acu14:latest" "awvs" "3443:3443" ""

# Contenedor BloodHound (puerto 7474)
run_docker "belane/bloodhound" "bloodhound" "7474:7474" "-e DISPLAY=unix$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix --device=/dev/dri:/dev/dri -v $(pwd)/bh-data:/data"

# Contenedor Nexpose (puerto 3780)
run_docker "vouu/nexpose:preview" "nexpose" "3780:3780" ""

# Contenedor Nexpose personalizado (puerto 49160)
run_docker "whithajess/dockernexpose" "nexpose_container" "49160:3780" ""

# Contenedor OpenVAS (puerto 443)
run_docker "mikesplain/openvas" "openvas" "443:443" ""
# Contenedor SpiderFoot (puerto 5001)
run_docker "dtagdevsec/spiderfoot:24.04.1" "spiderfoot" "5001:8080" ""

# Contenedor Nessus (puerto 8834)
run_docker "ramisec/nessus" "nessus" "8834:8834" ""

# Ejemplo: Detener contenedores (puedes comentar esta parte si no deseas detenerlos automáticamente)
stop_docker "web-check"
stop_docker "awvs"
stop_docker "bloodhound"
stop_docker "nexpose"
stop_docker "nexpose_container"
stop_docker "openvas"
stop_docker "spiderfoot"
stop_docker "nessus"

echo "Todos los contenedores se han configurado e iniciado correctamente."	

