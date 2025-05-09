// static/js/scanner_logic.js
document.addEventListener('DOMContentLoaded', () => {
    const toolListDiv = document.getElementById('toolList');
    const scanOutput = document.getElementById('scanOutput');
    const targetsTextarea = document.getElementById('targets');
    const jobIdDisplay = document.getElementById('jobIdDisplay');
    const jobStatusDisplay = document.getElementById('jobStatusDisplay');
    const overallProgressBar = document.getElementById('overallProgressBar');
    // const overallProgressBarContainer = document.getElementById('overallProgressBarContainer'); // Ya no se usa directamente aquí
    const currentJobInfoDiv = document.getElementById('currentJobInfo');
    const cancelJobButton = document.getElementById('cancelJobButton');
    const downloadJobZipLink = document.getElementById('downloadJobZip');
    const jobsListArea = document.getElementById('jobsListArea');
    const advancedOptionsDetails = document.querySelector('.advanced-options-container details');
    const toolSpecificCliParamsContainer = document.getElementById('toolSpecificCliParamsContainer'); // Nuevo contenedor para CLI

    // SCRIPT_ROOT será establecido por Flask en el HTML (en index.html).
    // La declaración let SCRIPT_ROOT = ""; que estaba aquí se ha eliminado para evitar errores de redeclaración.
    // Si SCRIPT_ROOT no está definido globalmente por alguna razón, se puede manejar así:
    if (typeof SCRIPT_ROOT === 'undefined') {
        console.error("SCRIPT_ROOT no fue definido globalmente por el HTML. Usando '' por defecto.");
        // En este caso, SCRIPT_ROOT se volvería una variable global implícita si se asigna sin 'const', 'let' o 'var'.
        // Es mejor asegurar que el HTML lo defina siempre. Si se necesita un fallback:
        // window.SCRIPT_ROOT = ""; // O manejar el error de otra forma.
        // Sin embargo, el <script> en index.html DEBE definirlo.
    }

    let appConfig = { tools: {}, profiles: {}, phases: {} }; // Para almacenar la configuración del backend
    let currentJobId = localStorage.getItem('currentJobId');
    let statusPollInterval;


    function logToTerminal(message, type = 'info', isHtml = false) {
        const entry = document.createElement('div');
        entry.classList.add('log-entry', type);
        const timestamp = new Date().toLocaleTimeString();
        let icon = 'ℹ️';
        if (type === 'error') icon = '❌';
        else if (type === 'warn') icon = '⚠️';
        else if (type === 'success') icon = '✅';
        else if (type === 'command') icon = '🛠️';

        if (isHtml) {
            entry.innerHTML = `<strong>[${timestamp}] ${icon}</strong> ${message}`;
        } else {
            entry.textContent = `[${timestamp}] ${icon} ${message}`;
        }
        scanOutput.appendChild(entry);
        scanOutput.scrollTop = scanOutput.scrollHeight;
    }

    async function fetchAppConfig() {
        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/config`); // Asume un endpoint /api/config
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            appConfig = await response.json();
            populateToolSelection();
            populateScanProfiles();
            populateAdvancedOptions(); // Para opciones globales y CLI dinámicas
        } catch (error) {
            logToTerminal(`Error al cargar la configuración de la aplicación: ${error}`, 'error');
            toolListDiv.innerHTML = '<p class="error">Error al cargar herramientas. Intente recargar la página.</p>';
        }
    }
    
    function populateScanProfiles() {
        const profilesContainer = document.querySelector('.scan-profiles');
        const existingButtons = profilesContainer.querySelectorAll('button[data-profile-name]');
        existingButtons.forEach(btn => btn.remove()); // Limpiar botones de perfiles previos si se regenera

        Object.keys(appConfig.profiles).forEach(profileName => {
            const profile = appConfig.profiles[profileName];
            const button = document.createElement('button');
            button.textContent = `${profile.icon || '🚀'} ${profileName}`;
            button.title = profile.description;
            button.dataset.profileName = profileName;
            button.onclick = () => applyScanProfile(profileName);
            // Insertar antes del botón "Desmarcar Todas"
            const deselectAllButton = profilesContainer.querySelector('button[onclick*="deselectAllTools()"]'); // Ajustado para ser más específico
            if (deselectAllButton) {
                profilesContainer.insertBefore(button, deselectAllButton);
            } else {
                profilesContainer.appendChild(button);
            }
        });
    }


    function populateToolSelection() {
        toolListDiv.innerHTML = '';
        let toolIdCounter = 0;

        // Agrupar herramientas por fase y luego por categoría
        const toolsByPhaseAndCategory = {};
        for (const toolKey in appConfig.tools) {
            const tool = appConfig.tools[toolKey];
            const phaseName = tool.phase; // 'phase' ya viene resuelto desde helpers.py
            const categoryName = tool.category;

            if (!toolsByPhaseAndCategory[phaseName]) {
                toolsByPhaseAndCategory[phaseName] = {};
            }
            if (!toolsByPhaseAndCategory[phaseName][categoryName]) {
                toolsByPhaseAndCategory[phaseName][categoryName] = [];
            }
            toolsByPhaseAndCategory[phaseName][categoryName].push({ ...tool, id: toolKey });
        }

        for (const phaseName in toolsByPhaseAndCategory) {
            const phaseId = `phase-${toolIdCounter++}`;
            const phaseDiv = document.createElement('div');
            phaseDiv.className = 'pentest-phase';
            phaseDiv.innerHTML = `
                <div class="pentest-phase-header">
                    <input type="checkbox" id="${phaseId}" data-type="phase">
                    <h4>${phaseName}</h4>
                </div>`;

            for (const categoryName in toolsByPhaseAndCategory[phaseName]) {
                const categoryId = `category-${toolIdCounter++}`;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'tool-category';
                categoryDiv.innerHTML = `
                    <div class="tool-category-header">
                        <input type="checkbox" id="${categoryId}" class="tool-category-checkbox" data-phase-parent-id="${phaseId}" data-type="category">
                        <h5>${categoryName}</h5>
                    </div>`;

                toolsByPhaseAndCategory[phaseName][categoryName].forEach(tool => {
                    const toolItemId = `tool-${tool.id}-${toolIdCounter++}`;
                    const toolItemDiv = document.createElement('div');
                    toolItemDiv.className = 'tool-item';
                    
                    let cliParamsHtml = '';
                    if (tool.cli_params_config && tool.cli_params_config.length > 0) {
                        cliParamsHtml += `<div class="tool-cli-params-group" id="cli-group-${tool.id}" style="display:none; margin-left: 25px; padding: 5px; border-left: 2px solid #440000;">`;
                        tool.cli_params_config.forEach(paramConf => {
                            cliParamsHtml += `<label for="cli-${tool.id}-${paramConf.name}">${paramConf.label}:</label>`;
                            if (paramConf.type === 'select') {
                                cliParamsHtml += `<select id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}">`;
                                paramConf.options.forEach(opt => {
                                    cliParamsHtml += `<option value="${opt}" ${opt === paramConf.default ? 'selected' : ''}>${opt}</option>`;
                                });
                                cliParamsHtml += `</select><br>`;
                            } else { // text, number
                                cliParamsHtml += `<input type="${paramConf.type || 'text'}" id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" placeholder="${paramConf.placeholder || ''}" value="${paramConf.default || ''}"><br>`;
                            }
                        });
                        cliParamsHtml += `</div>`;
                    }

                    toolItemDiv.innerHTML = `
                        <label for="${toolItemId}">
                            <input type="checkbox" id="${toolItemId}" name="selected_tools" value="${tool.id}" class="tool-item-checkbox" data-category-parent-id="${categoryId}" data-type="tool" ${tool.default_enabled ? 'checked' : ''}>
                            ${tool.name} ${tool.dangerous ? '<span class="tool-dangerous-indicator" title="Esta herramienta puede ser intrusiva o disruptiva">⚠️</span>' : ''}
                        </label>
                        <div class="tool-description">${tool.description}</div>
                        ${cliParamsHtml}
                    `;
                    categoryDiv.appendChild(toolItemDiv);
                });
                phaseDiv.appendChild(categoryDiv);
            }
            toolListDiv.appendChild(phaseDiv);
        }
        addCheckboxEventListeners();
        updateAllParentCheckboxes(); // Ensure correct initial state of parent checkboxes
    }

    function addCheckboxEventListeners() {
        toolListDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', handleCheckboxChange);
        });
    }

    function handleCheckboxChange(event) {
        const checkbox = event.target;
        const type = checkbox.dataset.type;

        if (type === 'phase') {
            const phaseId = checkbox.id;
            toolListDiv.querySelectorAll(`.tool-category-checkbox[data-phase-parent-id="${phaseId}"]`).forEach(catCb => {
                catCb.checked = checkbox.checked;
                catCb.indeterminate = false;
                toggleChildren(catCb, '.tool-item-checkbox', checkbox.checked);
            });
        } else if (type === 'category') {
            toggleChildren(checkbox, '.tool-item-checkbox', checkbox.checked);
            updateParentCheckboxState(checkbox.dataset.phaseParentId, '.tool-category-checkbox');
        } else if (type === 'tool') {
            updateParentCheckboxState(checkbox.dataset.categoryParentId, '.tool-item-checkbox');
            // Mostrar/ocultar CLI params para esta herramienta
            const cliGroup = document.getElementById(`cli-group-${checkbox.value}`);
            if (cliGroup) {
                cliGroup.style.display = checkbox.checked ? 'block' : 'none';
            }
        }
        // Asegurar que los parámetros CLI se muestren si la herramienta está marcada inicialmente
        // (Esta parte ya está cubierta por updateAllParentCheckboxes al final de populate y por la lógica de 'tool' arriba)
        // if (type === 'tool' && checkbox.checked) {
        // const cliGroup = document.getElementById(`cli-group-${checkbox.value}`);
        // if (cliGroup) cliGroup.style.display = 'block';
        // }
    }
    
    function toggleChildren(parentCheckbox, childrenSelector, isChecked) {
        const parentContainer = parentCheckbox.closest('.pentest-phase, .tool-category');
        parentContainer.querySelectorAll(childrenSelector + `[data-category-parent-id="${parentCheckbox.id}"]`).forEach(child => {
            child.checked = isChecked;
            child.indeterminate = false;
            // Visibilidad de CLI params para herramientas individuales
            if (child.dataset.type === 'tool') {
                const cliGroup = document.getElementById(`cli-group-${child.value}`);
                if (cliGroup) cliGroup.style.display = isChecked ? 'block' : 'none';
            }
        });
    }

    function updateParentCheckboxState(parentId, childrenSelectorClass) {
        if (!parentId) return;
        const parentCheckbox = document.getElementById(parentId);
        if (!parentCheckbox) return;

        // Determinar el tipo de hijos a buscar (categorías para una fase, o herramientas para una categoría)
        let actualChildrenSelector = '';
        if (parentCheckbox.dataset.type === 'phase') {
            actualChildrenSelector = `.tool-category-checkbox[data-phase-parent-id="${parentId}"]`;
        } else if (parentCheckbox.dataset.type === 'category') {
            actualChildrenSelector = `.tool-item-checkbox[data-category-parent-id="${parentId}"]`;
        } else {
            return; // No es un padre conocido
        }
        
        const children = Array.from(toolListDiv.querySelectorAll(actualChildrenSelector));
        if (children.length === 0 && parentCheckbox.dataset.type === 'phase') { // Si una fase no tiene categorías (raro), basarse en herramientas directas (si existieran)
             // Esta lógica puede necesitar ajuste si hay herramientas directas bajo fases, lo cual no es la estructura actual.
        }


        const allChecked = children.every(child => child.checked);
        const someChecked = children.some(child => child.checked || child.indeterminate);

        parentCheckbox.checked = allChecked && children.length > 0; // Solo 'checked' si hay hijos y todos están marcados
        parentCheckbox.indeterminate = !allChecked && someChecked;

        // Propagate upwards (de categoría a fase)
        if (parentCheckbox.dataset.type === 'category' && parentCheckbox.dataset.phaseParentId) {
            updateParentCheckboxState(parentCheckbox.dataset.phaseParentId, '.tool-category-checkbox'); // El selector aquí es para los hijos del padre (fase)
        }
    }

    function updateAllParentCheckboxes() {
        // Actualizar categorías basadas en herramientas
        toolListDiv.querySelectorAll('.tool-category-checkbox').forEach(catCb => {
            updateParentCheckboxState(catCb.id, '.tool-item-checkbox'); // Los hijos de una categoría son .tool-item-checkbox
        });
        // Actualizar fases basadas en categorías
        toolListDiv.querySelectorAll('input[data-type="phase"]').forEach(phaseCb => {
            updateParentCheckboxState(phaseCb.id, '.tool-category-checkbox'); // Los hijos de una fase son .tool-category-checkbox
        });
        // Asegurar que los CLI params de las herramientas marcadas por defecto se muestren
        toolListDiv.querySelectorAll('.tool-item-checkbox:checked').forEach(toolCb => {
            const cliGroup = document.getElementById(`cli-group-${toolCb.value}`);
            if (cliGroup) cliGroup.style.display = 'block';
        });
    }
    
    window.applyScanProfile = function(profileName) {
        applyToolPreset('none'); // Desmarcar todo primero
        const profile = appConfig.profiles[profileName];
        if (profile && profile.tools) {
            profile.tools.forEach(toolId => {
                const toolCheckbox = toolListDiv.querySelector(`input[name="selected_tools"][value="${toolId}"]`);
                if (toolCheckbox) {
                    toolCheckbox.checked = true;
                    // Disparar evento change para actualizar padres y mostrar CLI
                    toolCheckbox.dispatchEvent(new Event('change', { bubbles: true })); // Asegurar que el evento burbujee
                }
            });

            // Aplicar parámetros específicos del perfil
            if (profile.params_override) {
                for (const toolId in profile.params_override) {
                    const toolParams = profile.params_override[toolId];
                    for (const paramName in toolParams) {
                        const inputField = document.getElementById(`cli-${toolId}-${paramName}`);
                        if (inputField) {
                            inputField.value = toolParams[paramName];
                        }
                    }
                }
            }
            updateAllParentCheckboxes(); // Re-evaluar estado de checkboxes padres
        }
    }

    window.applyToolPreset = function(presetName) {
        if (presetName === 'none') {
            toolListDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.checked = false;
                checkbox.indeterminate = false;
                if (checkbox.dataset.type === 'tool') { // Ocultar CLI params si se desmarca
                    const cliGroup = document.getElementById(`cli-group-${checkbox.value}`);
                    if (cliGroup) cliGroup.style.display = 'none';
                }
            });
        }
        // Podrías añadir más presets aquí (ej: 'all', 'safe', etc.)
    }

    async function startScan() {
        const targets = targetsTextarea.value.trim().split('\n').filter(t => t.trim() !== '');
        if (targets.length === 0) {
            logToTerminal("Por favor, ingrese al menos un objetivo.", "error");
            return;
        }

        const selectedToolsPayload = [];
        document.querySelectorAll('input[name="selected_tools"]:checked').forEach(cb => {
            const toolId = cb.value;
            const toolConfig = appConfig.tools[toolId];
            let params = {};
            if (toolConfig && toolConfig.cli_params_config) {
                toolConfig.cli_params_config.forEach(pConf => {
                    const inputField = document.getElementById(`cli-${toolId}-${pConf.name}`);
                    if (inputField && inputField.value.trim() !== '') {
                        params[pConf.name] = inputField.value;
                    } else if (pConf.default) {
                        params[pConf.name] = pConf.default; // Usar default si está vacío
                    }
                });
            }
            selectedToolsPayload.push({ id: toolId, cli_params: params });
        });

        if (selectedToolsPayload.length === 0) {
            logToTerminal("Por favor, seleccione al menos una herramienta de escaneo.", "error");
            return;
        }
        
        const advancedScanOptions = {
            customScanTime: document.getElementById('customScanTime') ? document.getElementById('customScanTime').value : null,
            followRedirects: document.getElementById('followRedirects') ? document.getElementById('followRedirects').value : null,
            // Añadir más opciones avanzadas globales aquí
        };


        logToTerminal(`Iniciando escaneo para objetivo(s): ${targets.join(', ')}...`, 'info');
        currentJobInfoDiv.style.display = 'block';
        jobIdDisplay.textContent = 'Generando...';
        jobStatusDisplay.textContent = 'Iniciando...';
        overallProgressBar.style.width = '0%';
        overallProgressBar.textContent = '0%';
        cancelJobButton.style.display = 'inline-block';
        downloadJobZipLink.style.display = 'none';
        downloadJobZipLink.classList.add('disabled');


        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    targets, 
                    tools: selectedToolsPayload,
                    advanced_options: advancedScanOptions 
                }),
            });

            const data = await response.json();
            if (response.ok) {
                currentJobId = data.job_id;
                jobIdDisplay.textContent = currentJobId;
                logToTerminal(`Escaneo iniciado con Job ID: ${currentJobId}`, "success");
                localStorage.setItem('currentJobId', currentJobId);
                clearTimeout(statusPollInterval); // Limpiar sondeo anterior
                refreshStatus(currentJobId, true); // Iniciar sondeo para el nuevo job
                loadJobs(); // Actualizar lista de historial
            } else {
                logToTerminal(`Error al iniciar escaneo (HTTP ${response.status}): ${data.error || 'Error desconocido'}`, "error");
                currentJobInfoDiv.style.display = 'none';
            }
        } catch (error) {
            logToTerminal(`Error de red al iniciar escaneo: ${error.message || error}`, "error");
            currentJobInfoDiv.style.display = 'none';
        }
    }
    const scanButton = document.getElementById('startScanButton');
    // CORRECCIÓN: Usar getElementById para 'refreshStatusButton'
    const refreshButton = document.getElementById('refreshStatusButton'); 
    
    if(scanButton) {
        scanButton.onclick = startScan;
    } else {
        console.error('No se encontró el botón startScanButton');
    }
    
    if(refreshButton) {
        refreshButton.onclick = () => refreshStatus(); // No necesita argumento, refreshStatus lo maneja
    } else {
        // Mensaje actualizado para reflejar que se busca por ID
        console.error('No se encontró el botón con ID refreshStatusButton'); 
    }

    async function refreshStatus(jobIdToRefresh = null, initialCall = false) {
        const effectiveJobId = jobIdToRefresh || currentJobId;
        if (!effectiveJobId) {
            currentJobInfoDiv.style.display = 'none';
            cancelJobButton.style.display = 'none';
            downloadJobZipLink.style.display = 'none';
            downloadJobZipLink.classList.add('disabled');
            return;
        }

        // Si es una llamada inicial para un nuevo job, mostrar info inmediatamente
        if (initialCall) {
            jobIdDisplay.textContent = effectiveJobId;
            currentJobInfoDiv.style.display = 'block';
            cancelJobButton.style.display = 'inline-block'; // O 'none' si el job ya podría estar completo
            downloadJobZipLink.style.display = 'none';
            downloadJobZipLink.classList.add('disabled');
        }


        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/status/${effectiveJobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    logToTerminal(`Job ID ${effectiveJobId} no encontrado. Pudo haber sido eliminado o nunca existió.`, "warn");
                    if (effectiveJobId === currentJobId) { // Solo limpiar si es el job "activo" actual
                        localStorage.removeItem('currentJobId');
                        currentJobId = null;
                        currentJobInfoDiv.style.display = 'none';
                        clearTimeout(statusPollInterval);
                    }
                } else {
                    const errorData = await response.json().catch(() => ({ error: "Error desconocido al obtener estado." }));
                    logToTerminal(`Error al obtener estado (HTTP ${response.status}): ${errorData.error}`, "error");
                }
                return;
            }

            const data = await response.json();
            jobIdDisplay.textContent = data.job_id; // Actualizar por si acaso
            jobStatusDisplay.textContent = data.status;
            overallProgressBar.style.width = `${data.overall_progress || 0}%`;
            overallProgressBar.textContent = `${data.overall_progress || 0}%`;
            currentJobInfoDiv.style.display = 'block'; // Asegurar que esté visible

            // Limpiar logs antiguos de la terminal si el job es diferente o está iniciando
            if (scanOutput.dataset.currentJobLog !== data.job_id && initialCall) { // Limpiar solo en llamada inicial de un nuevo job
                scanOutput.innerHTML = ''; 
                logToTerminal(`Mostrando logs para Job ID: ${data.job_id}`, 'info');
                scanOutput.dataset.currentJobLog = data.job_id;
            }
            
            // Mostrar logs del job (el backend debería enviar solo logs nuevos o un subconjunto)
            if (data.logs && Array.isArray(data.logs)) {
                data.logs.forEach(log => {
                    // Una forma simple de evitar duplicados si el backend reenvía todos los logs
                    // Lo ideal es que el backend envíe solo logs nuevos desde el último poll.
                    // Esta comprobación puede ser costosa si hay muchos logs.
                    // if (!scanOutput.innerHTML.includes(log.message)) { // Esta comprobación puede ser ineficiente
                        logToTerminal(log.message, log.type || 'info', log.is_html || false);
                    // }
                });
            }


            if (data.status === 'COMPLETED' || data.status === 'CANCELLED' || data.status === 'ERROR') {
                cancelJobButton.style.display = 'none';
                if (data.zip_path) {
                    downloadJobZipLink.href = `${SCRIPT_ROOT}${data.zip_path}`; // Asegurar SCRIPT_ROOT si es necesario
                    downloadJobZipLink.style.display = 'inline-block';
                    downloadJobZipLink.classList.remove('disabled');

                }
                if (effectiveJobId === currentJobId) { // Si el job "activo" ha terminado
                    // No remover currentJobId de localStorage aquí, para que la UI pueda mostrarlo hasta que el usuario seleccione otro.
                    // currentJobId = null; // No establecer a null para que refreshStatus manual aún funcione
                }
                clearTimeout(statusPollInterval); // Detener sondeo
                loadJobs(); // Actualizar la lista para reflejar el estado final
            } else { // PENDING, RUNNING
                cancelJobButton.style.display = 'inline-block'; // Mantener visible si está en curso
                downloadJobZipLink.style.display = 'none';
                downloadJobZipLink.classList.add('disabled');
                clearTimeout(statusPollInterval); // Limpiar sondeo anterior
                statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 5000);
            }

        } catch (error) {
            logToTerminal(`Error de red al obtener estado: ${error.message || error}`, "error");
            clearTimeout(statusPollInterval);
            statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 10000); // Reintentar tras 10s
        }
    }
    // ELIMINADA: La siguiente línea es redundante y causaba el error TypeError debido al selector incorrecto.
    // La asignación de onclick para refreshButton ya se hace arriba de forma segura.
    // document.querySelector('button[onclick="refreshStatus()"]').onclick = () => refreshStatus();


    async function cancelScan() {
        const jobIdToCancel = jobIdDisplay.textContent; // Usar el ID mostrado en la UI
        if (!jobIdToCancel || jobIdToCancel === 'Generando...') {
            logToTerminal("No hay un trabajo específico seleccionado o activo para cancelar.", "warn");
            return;
        }
        if (!confirm(`¿Está seguro de que desea cancelar el trabajo ${jobIdToCancel}?`)) {
            return;
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/cancel/${jobIdToCancel}`, { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                logToTerminal(`Solicitud de cancelación enviada para el trabajo ${jobIdToCancel}.`, "info");
                jobStatusDisplay.textContent = "Cancelando...";
                cancelJobButton.style.display = 'none'; // Ocultar inmediatamente
                clearTimeout(statusPollInterval); // Detener sondeo temporalmente
                statusPollInterval = setTimeout(() => refreshStatus(jobIdToCancel), 2000); // Actualizar estado pronto
            } else {
                logToTerminal(`Error al cancelar escaneo (HTTP ${response.status}): ${data.error || 'Error desconocido'}`, "error");
            }
        } catch (error) {
            logToTerminal(`Error de red al cancelar escaneo: ${error.message || error}`, "error");
        }
    }
    if (cancelJobButton) { // Asegurarse que el botón existe antes de asignar
        cancelJobButton.onclick = cancelScan;
    }


    async function loadJobs() {
        jobsListArea.innerHTML = '<li>Cargando trabajos...</li>';
        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/jobs`);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            const jobs = await response.json();
            
            jobsListArea.innerHTML = ''; // Limpiar
            if (jobs.length === 0) {
                jobsListArea.innerHTML = '<li>No hay trabajos anteriores.</li>';
                return;
            }
            jobs.forEach(job => {
                const li = document.createElement('li');
                let targetsDisplay = Array.isArray(job.targets) ? job.targets.join(', ') : (job.targets || 'N/A');
                if (targetsDisplay.length > 50) targetsDisplay = targetsDisplay.substring(0, 47) + '...';

                li.innerHTML = `
                    <div class="job-summary">
                        <strong>ID:</strong> ${job.id} <br>
                        <strong>Estado:</strong> <span class="job-status-${job.status.toLowerCase()}">${job.status}</span> <br>
                        <strong>Fecha:</strong> ${job.timestamp ? new Date(job.timestamp).toLocaleString() : 'N/A'} <br>
                        <strong>Objetivos:</strong> ${targetsDisplay}
                    </div>
                    <div class="job-actions">
                        <button class="button-like view-details-btn">Ver Detalles</button>
                        ${job.zip_path ? `<a href="${SCRIPT_ROOT}${job.zip_path}" class="button-like download-zip-btn" target="_blank">Descargar ZIP</a>` : ''}
                    </div>
                `;
                li.querySelector('.view-details-btn').onclick = (e) => {
                    e.stopPropagation(); 
                    viewJobDetails(job.id);
                };
                jobsListArea.appendChild(li);
            });
        } catch (error) {
            logToTerminal(`Error al cargar historial de trabajos: ${error.message || error}`, "error");
            jobsListArea.innerHTML = '<li>Error al cargar trabajos.</li>';
        }
    }

    function viewJobDetails(jobId) {
        logToTerminal(`Cargando detalles para el trabajo ${jobId}...`, "info");
        currentJobId = jobId; // Actualizar el currentJobId global del frontend
        localStorage.setItem('currentJobId', jobId); // Guardar para futuras recargas de página
        clearTimeout(statusPollInterval); // Detener cualquier sondeo anterior
        // Limpiar terminal para logs del nuevo job ANTES de llamar a refreshStatus
        scanOutput.innerHTML = ''; 
        scanOutput.dataset.currentJobLog = jobId; // Marcar la terminal
        refreshStatus(jobId, true); // Iniciar sondeo para este job, es una llamada inicial
    }
    
    // Función global para desmarcar todas las herramientas, referenciada desde index.html
    window.deselectAllTools = function() {
        applyToolPreset('none');
    }

    // Inicialización
    fetchAppConfig().then(() => {
        loadJobs();
        if (currentJobId) {
            viewJobDetails(currentJobId); // Cargar detalles del último job activo si existe
        } else {
            currentJobInfoDiv.style.display = 'none'; // Ocultar si no hay job activo
        }
    });
});