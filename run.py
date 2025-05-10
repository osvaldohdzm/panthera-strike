from app import create_app

app = create_app()

if __name__ == '__main__':
    # La configuración del host y puerto podría cargarse desde la configuración de la app
    app.run(host='0.0.0.0', port=5000, debug=True)