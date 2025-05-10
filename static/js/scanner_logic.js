// static/js/scanner_logic.js
document.addEventListener('DOMContentLoaded', () => {
    const toolListDiv = document.getElementById('toolList');
    const scanOutput = document.getElementById('scanOutput');
    const targetsTextarea = document.getElementById('targets');
    const jobIdDisplay = document.getElementById('jobIdDisplay');
    const jobStatusDisplay = document.getElementById('jobStatusDisplay');
    const jobStatusBadge = document.getElementById('jobStatusBadge'); // NUEVO: Para el badge de estado
    const overallProgressBar = document.getElementById('overallProgressBar');
    const currentJobInfoDiv = document.getElementById('currentJobInfo');
    const jobInfoPanel = document.getElementById('job-info-panel');
    const cancelJobButton = document.getElementById('cancelJobButton');
    const downloadJobZipLink = document.getElementById('downloadJobZip');
    const jobsListArea = document.getElementById('jobsListArea');

    const importTargetsButton = document.getElementById('importTargetsButton');
    const importTargetsFile = document.getElementById('importTargetsFile');
    const clearTargetsButton = document.getElementById('clearTargetsButton'); // NUEVO
    const targetsCountDisplay = document.getElementById('targetsCount'); // NUEVO

    const copyLogButton = document.getElementById('copyLogButton');
    const downloadLogButton = document.getElementById('downloadLogButton');
    const scanButton = document.getElementById('startScanButton');
    const refreshButton = document.getElementById('refreshStatusButton');

    if (typeof SCRIPT_ROOT === 'undefined') {
        console.warn("SCRIPT_ROOT no fue definido globalmente por el HTML. Usando '' por defecto, esto podría no funcionar si la app no está en la raíz.");
        window.SCRIPT_ROOT = ""; // Asegurar que SCRIPT_ROOT exista
    }

    let appConfig = { tools: {}, profiles: {}, phases: {} };
    let currentJobId = localStorage.getItem('currentJobId');
    let statusPollInterval;
    // let logEntryCounter = 0; // Ya no se usa para animación secuencial aquí

    // NUEVO: Función para actualizar contador de objetivos
    function updateTargetsCount() {
        if (targetsTextarea && targetsCountDisplay) {
            const targets = targetsTextarea.value.trim().split('\n').filter(t => t.trim() !== '');
            targetsCountDisplay.textContent = `${targets.length} objetivo(s)`;
        }
    }

    if (targetsTextarea) {
        targetsTextarea.addEventListener('input', updateTargetsCount);
    }

    if (clearTargetsButton && targetsTextarea) {
        clearTargetsButton.onclick = () => {
            targetsTextarea.value = '';
            updateTargetsCount();
            logToTerminal("Lista de objetivos borrada.", "info");
        };
    }


    function logToTerminal(message, type = 'info', isHtml = false) {
        const entry = document.createElement('div');
        // MODIFICADO: Clases para mejor estilizado y tipo
        entry.classList.add('log-entry', `log-type-${type}`);

        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        let iconClass = 'icon-info-circle'; // Default
        if (type === 'error') iconClass = 'icon-times-circle';
        else if (type === 'warn') iconClass = 'icon-exclamation-triangle';
        else if (type === 'success') iconClass = 'icon-check-circle';
        else if (type === 'command') iconClass = 'icon-terminal';

        // MODIFICADO: Uso de <i> para iconos, más flexible con CSS/librerías
        const iconSpan = `<span class="log-icon"><i class="${iconClass}"></i></span>`;
        const timestampSpan = `<span class="log-timestamp">[${timestamp}]</span>`;
        const messageSpan = `<span class="log-message-content"></span>`;

        entry.innerHTML = `${iconSpan}${timestampSpan}${messageSpan}`;

        if (isHtml) {
            entry.querySelector('.log-message-content').innerHTML = message;
        } else {
            entry.querySelector('.log-message-content').textContent = message;
        }
        scanOutput.appendChild(entry);
        scanOutput.scrollTop = scanOutput.scrollHeight;
    }

    async function fetchAppConfig() {
        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/config`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            appConfig = await response.json();
            populateToolSelection();
            populateScanProfiles();
        } catch (error) {
            logToTerminal(`Error al cargar la configuración de la aplicación: ${error}`, 'error');
            toolListDiv.innerHTML = '<p class="error-message">Error al cargar herramientas. Intente recargar la página.</p>';
        }
    }

    function populateScanProfiles() {
        const profilesContainer = document.querySelector('.scan-profiles-buttons'); // MODIFICADO: Selector más específico
        if (!profilesContainer) return;

        profilesContainer.innerHTML = ''; // Limpiar botones existentes

        Object.keys(appConfig.profiles).forEach(profileName => {
            const profile = appConfig.profiles[profileName];
            const button = document.createElement('button');
            button.className = 'button-profile'; // NUEVO: Clase para estilizar
            // MODIFICADO: Usar <i> para iconos y span para texto
            button.innerHTML = `<i class="${profile.icon_class || 'icon-profile'}"></i> <span>${profileName}</span>`;
            button.title = profile.description;
            button.dataset.profileName = profileName;
            button.onclick = () => applyScanProfile(profileName);
            profilesContainer.appendChild(button);
        });
        // Botón de desmarcar todas podría ir aquí o en el HTML directamente
        const deselectAllButton = document.createElement('button');
        deselectAllButton.className = 'button-profile-deselect';
        deselectAllButton.innerHTML = '<i class="icon-square-o"></i> <span>Desmarcar Todas</span>';
        deselectAllButton.onclick = () => deselectAllTools();
        profilesContainer.appendChild(deselectAllButton);
    }

    function populateToolSelection() {
        toolListDiv.innerHTML = '';
        let uniqueIdCounter = 0;

        const toolsByPhaseAndCategory = {};
        for (const toolKey in appConfig.tools) {
            const tool = appConfig.tools[toolKey];
            const phaseName = tool.phase;
            const categoryName = tool.category;

            if (!toolsByPhaseAndCategory[phaseName]) toolsByPhaseAndCategory[phaseName] = {};
            if (!toolsByPhaseAndCategory[phaseName][categoryName]) toolsByPhaseAndCategory[phaseName][categoryName] = [];
            toolsByPhaseAndCategory[phaseName][categoryName].push({ ...tool, id: toolKey });
        }

        for (const phaseName in toolsByPhaseAndCategory) {
            const phaseId = `phase-toggle-${uniqueIdCounter++}`;
            const phaseDiv = document.createElement('div');
            phaseDiv.className = 'pentest-phase';

            const phaseDisplayName = appConfig.phases[phaseName]?.name || phaseName; // NUEVO: Usar nombre de fase de config si existe
            const phaseIconClass = appConfig.phases[phaseName]?.icon_class || 'icon-layer-group'; // NUEVO

            const phaseHeader = document.createElement('div');
            phaseHeader.className = 'pentest-phase-header';
            phaseHeader.innerHTML = `
                <label class="toggle-switch">
                    <input type="checkbox" id="${phaseId}" data-type="phase">
                    <span class="slider"></span>
                </label>
                <h4><i class="${phaseIconClass}"></i> ${phaseDisplayName}</h4>`;
            phaseDiv.appendChild(phaseHeader);

            for (const categoryName in toolsByPhaseAndCategory[phaseName]) {
                const categoryId = `category-toggle-${uniqueIdCounter++}`;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'tool-category';

                // MODIFICADO: Usar icono de config o default
                const categoryConfig = toolsByPhaseAndCategory[phaseName][categoryName][0]; // Asume que todas las herramientas en cat tienen misma config de cat
                const categoryIconClass = categoryConfig?.category_icon_class || 'icon-folder';
                const categoryDisplayName = categoryConfig?.category_display_name || categoryName;


                const categoryHeader = document.createElement('div');
                categoryHeader.className = 'tool-category-header';
                categoryHeader.innerHTML = `
                    <label class="toggle-switch">
                        <input type="checkbox" id="${categoryId}" class="tool-category-checkbox" data-phase-parent-id="${phaseId}" data-type="category">
                        <span class="slider"></span>
                    </label>
                    <h5><i class="${categoryIconClass}"></i> ${categoryDisplayName}</h5>
                    <span class="accordion-arrow"><i class="icon-chevron-down"></i></span>`; // MODIFICADO: Icono de acordeón

                const toolItemsContainer = document.createElement('div');
                toolItemsContainer.className = 'tool-items-container'; // Por defecto colapsado (CSS)

                categoryHeader.onclick = (e) => {
                    if (e.target.type === 'checkbox' || e.target.classList.contains('slider') || e.target.closest('.toggle-switch')) return;
                    toolItemsContainer.classList.toggle('expanded');
                    const arrowIcon = categoryHeader.querySelector('.accordion-arrow i');
                    if (arrowIcon) {
                        arrowIcon.className = toolItemsContainer.classList.contains('expanded') ? 'icon-chevron-up' : 'icon-chevron-down';
                    }
                };
                categoryDiv.appendChild(categoryHeader);

                toolsByPhaseAndCategory[phaseName][categoryName].forEach(tool => {
                    const toolItemId = `tool-toggle-${tool.id}-${uniqueIdCounter++}`;
                    const toolItemDiv = document.createElement('div');
                    toolItemDiv.className = 'tool-item';

                    let cliParamsHtml = '';
                    if (tool.cli_params_config && tool.cli_params_config.length > 0) {
                        cliParamsHtml += `<div class="tool-cli-params-group" id="cli-group-${tool.id}" style="display:none;"><h6><i class="icon-sliders-h"></i> Parámetros Adicionales:</h6>`;
                        tool.cli_params_config.forEach(paramConf => {
                            // MODIFICADO: Estructura de label e input para mejor layout con CSS
                            cliParamsHtml += `<div class="cli-param-row">
                                                <label for="cli-${tool.id}-${paramConf.name}" title="${paramConf.description || ''}">${paramConf.label}:</label>`;
                            if (paramConf.type === 'select') {
                                cliParamsHtml += `<select id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" title="${paramConf.description || ''}">`;
                                paramConf.options.forEach(opt => {
                                    cliParamsHtml += `<option value="${opt.value || opt}" ${(opt.value || opt) === paramConf.default ? 'selected' : ''}>${opt.label || opt}</option>`;
                                });
                                cliParamsHtml += `</select>`;
                            } else {
                                cliParamsHtml += `<input type="${paramConf.type || 'text'}" id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" placeholder="${paramConf.placeholder || ''}" value="${paramConf.default || ''}" title="${paramConf.description || ''}">`;
                            }
                            cliParamsHtml += `</div>`; // Cierre de cli-param-row
                        });
                        cliParamsHtml += `</div>`;
                    }

                    // MODIFICADO: Icono para herramienta, y tooltip para descripción
                    const toolIconClass = tool.icon_class || 'icon-cog';
                    const dangerousIndicator = tool.dangerous ? `<span class="tool-dangerous-indicator" title="Esta herramienta puede ser intrusiva o disruptiva"><i class="icon-exclamation-triangle"></i></span>` : '';

                    toolItemDiv.innerHTML = `
                        <div class="tool-item-main">
                            <label class="toggle-switch">
                                <input type="checkbox" id="${toolItemId}" name="selected_tools" value="${tool.id}" class="tool-item-checkbox" data-category-parent-id="${categoryId}" data-type="tool" ${tool.default_enabled ? 'checked' : ''}>
                                <span class="slider"></span>
                            </label>
                            <span class="tool-icon"><i class="${toolIconClass}"></i></span>
                            <span class="toggle-label" title="${tool.description || tool.name}">${tool.name}</span>
                            ${dangerousIndicator}
                        </div>
                        <div class="tool-details" style="display:none;"> ${cliParamsHtml}
                        </div>
                    `;
                    // Lógica para mostrar/ocultar tool.description y cliParamsHtml si se selecciona la herramienta
                    const toolCheckboxInput = toolItemDiv.querySelector('.tool-item-checkbox');
                    toolCheckboxInput.addEventListener('change', (e) => {
                        const cliGroup = toolItemDiv.querySelector(`#cli-group-${e.target.value}`);
                        const toolDetails = toolItemDiv.querySelector('.tool-details');
                        if (cliGroup) { // Si hay parámetros CLI, se gestionan en handleCheckboxChange
                            if (toolDetails) toolDetails.style.display = e.target.checked ? 'block' : 'none'; // Mostrar/ocultar el contenedor de detalles
                        }
                        // Si no hay CLI params, podrías querer mostrar la descripción de todas formas
                        // else if (toolDetails && tool.description) {
                        //    toolDetails.style.display = e.target.checked ? 'block' : 'none';
                        // }

                    });

                    toolItemsContainer.appendChild(toolItemDiv);
                });
                categoryDiv.appendChild(toolItemsContainer);
                phaseDiv.appendChild(categoryDiv);
            }
            toolListDiv.appendChild(phaseDiv);
        }
        addCheckboxEventListeners();
        updateAllParentCheckboxes();
        // Por defecto, colapsar todas las categorías y actualizar flechas
        document.querySelectorAll('.tool-items-container').forEach(container => {
            container.classList.remove('expanded');
            const arrowIcon = container.previousElementSibling.querySelector('.accordion-arrow i');
            if (arrowIcon) arrowIcon.className = 'icon-chevron-down';
        });
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
                toggleChildren(catCb, checkbox.checked);
            });
        } else if (type === 'category') {
            toggleChildren(checkbox, checkbox.checked);
            updateParentCheckboxState(checkbox.dataset.phaseParentId);
        } else if (type === 'tool') {
            updateParentCheckboxState(checkbox.dataset.categoryParentId);
            const toolDetailsDiv = checkbox.closest('.tool-item').querySelector('.tool-details');
            const cliGroup = document.getElementById(`cli-group-${checkbox.value}`);

            if (toolDetailsDiv) { // Contenedor general de detalles
                toolDetailsDiv.style.display = checkbox.checked ? 'block' : 'none';
            }
            if (cliGroup) { // Específico para grupo CLI
                cliGroup.style.display = checkbox.checked ? 'block' : 'none';
            }
        }
    }

    function toggleChildren(parentCheckbox, isChecked) {
        const parentType = parentCheckbox.dataset.type;
        let childrenSelector = '';
        if (parentType === 'category') {
            childrenSelector = `.tool-item-checkbox[data-category-parent-id="${parentCheckbox.id}"]`;
        }

        if (childrenSelector) {
            // MODIFICADO: Búsqueda de hijos más robusta dentro del contenedor de la categoría
            const categoryDiv = parentCheckbox.closest('.tool-category');
            if (!categoryDiv) return;

            categoryDiv.querySelectorAll(childrenSelector).forEach(childCb => {
                childCb.checked = isChecked;
                childCb.indeterminate = false;
                if (childCb.dataset.type === 'tool') {
                    const toolDetailsDiv = childCb.closest('.tool-item').querySelector('.tool-details');
                    const cliGroup = document.getElementById(`cli-group-${childCb.value}`);
                    if (toolDetailsDiv) {
                        toolDetailsDiv.style.display = isChecked ? 'block' : 'none';
                    }
                    if (cliGroup) cliGroup.style.display = isChecked ? 'block' : 'none';
                }
            });
        }
    }

    function updateParentCheckboxState(parentId) {
        if (!parentId) return;
        const parentCheckbox = document.getElementById(parentId);
        if (!parentCheckbox) return;

        const parentType = parentCheckbox.dataset.type;
        let childrenCheckboxes;

        if (parentType === 'phase') {
            childrenCheckboxes = toolListDiv.querySelectorAll(`.tool-category-checkbox[data-phase-parent-id="${parentId}"]`);
        } else if (parentType === 'category') {
            // MODIFICADO: Búsqueda de hijos más robusta dentro del contenedor de la categoría
            const categoryDiv = parentCheckbox.closest('.tool-category');
            if (!categoryDiv) return;
            childrenCheckboxes = categoryDiv.querySelectorAll(`.tool-item-checkbox[data-category-parent-id="${parentId}"]`);
        } else {
            return;
        }

        const childrenArray = Array.from(childrenCheckboxes);
        const allChecked = childrenArray.length > 0 && childrenArray.every(child => child.checked && !child.indeterminate);
        const someChecked = childrenArray.some(child => child.checked || child.indeterminate);

        parentCheckbox.checked = allChecked;
        parentCheckbox.indeterminate = !allChecked && someChecked;

        if (parentType === 'category' && parentCheckbox.dataset.phaseParentId) {
            updateParentCheckboxState(parentCheckbox.dataset.phaseParentId);
        }
    }

    function updateAllParentCheckboxes() {
        toolListDiv.querySelectorAll('.tool-item-checkbox:checked').forEach(toolCb => {
            const toolDetailsDiv = toolCb.closest('.tool-item').querySelector('.tool-details');
            const cliGroup = document.getElementById(`cli-group-${toolCb.value}`);
            if (toolDetailsDiv) toolDetailsDiv.style.display = 'block';
            if (cliGroup) cliGroup.style.display = 'block';
        });
        toolListDiv.querySelectorAll('.tool-category-checkbox').forEach(catCb => {
            updateParentCheckboxState(catCb.id);
        });
        toolListDiv.querySelectorAll('input[data-type="phase"]').forEach(phaseCb => {
            updateParentCheckboxState(phaseCb.id);
        });
    }

    window.applyScanProfile = function (profileName) {
        deselectAllTools();
        const profile = appConfig.profiles[profileName];
        if (profile && profile.tools) {
            profile.tools.forEach(toolId => {
                const toolCheckbox = toolListDiv.querySelector(`input[name="selected_tools"][value="${toolId}"]`);
                if (toolCheckbox) {
                    toolCheckbox.checked = true;
                    toolCheckbox.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });

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
            logToTerminal(`Perfil '${profileName}' aplicado.`, 'success');
        }
        updateAllParentCheckboxes();
        // NUEVO: Resaltar perfil activo (requiere CSS)
        document.querySelectorAll('.button-profile').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.profileName === profileName) {
                btn.classList.add('active');
            }
        });
    }

    window.deselectAllTools = function () {
        toolListDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
            checkbox.indeterminate = false;
            if (checkbox.dataset.type === 'tool') {
                const toolDetailsDiv = checkbox.closest('.tool-item').querySelector('.tool-details');
                const cliGroup = document.getElementById(`cli-group-${checkbox.value}`);
                if (toolDetailsDiv) toolDetailsDiv.style.display = 'none';
                if (cliGroup) cliGroup.style.display = 'none';
            }
        });
        // NUEVO: Quitar resaltado de perfil activo
        document.querySelectorAll('.button-profile.active').forEach(btn => btn.classList.remove('active'));
        logToTerminal('Todas las herramientas deseleccionadas.', 'info');
    }

    async function startScan() {
        const targets = targetsTextarea.value.trim().split('\n').filter(t => t.trim() !== '');
        if (targets.length === 0) {
            logToTerminal("Por favor, ingrese al menos un objetivo.", "error");
            targetsTextarea.focus();
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
                        params[pConf.name] = pConf.default;
                    }
                });
            }
            selectedToolsPayload.push({ id: toolId, cli_params: params });
        });

        if (selectedToolsPayload.length === 0) {
            logToTerminal("Por favor, seleccione al menos una herramienta de escaneo.", "error");
            return;
        }

        // MODIFICADO: Obtener opciones avanzadas de forma más robusta
        const advancedScanOptions = {
            customScanTime: document.getElementById('customScanTime')?.value || null,
            followRedirects: document.getElementById('followRedirects')?.checked || false, // Asumiendo checkbox
            scanIntensity: document.getElementById('scanIntensity')?.value || 'normal', // Asumiendo select
        };

        logToTerminal(`Iniciando escaneo para objetivo(s): ${targets.join(', ')}...`, 'command');
        if (jobInfoPanel) jobInfoPanel.style.display = 'block';
        currentJobInfoDiv.style.display = 'block';
        jobIdDisplay.textContent = 'Generando...';
        if (jobStatusBadge) { // MODIFICADO: Actualizar badge
            jobStatusBadge.textContent = 'Iniciando';
            jobStatusBadge.className = 'status-badge status-pending';
        }
        overallProgressBar.style.width = '0%';
        overallProgressBar.setAttribute('aria-valuenow', '0'); // NUEVO: Accesibilidad
        overallProgressBar.textContent = '0%';
        cancelJobButton.style.display = 'inline-block';
        downloadJobZipLink.style.display = 'none';
        downloadJobZipLink.classList.add('disabled');
        if (scanButton) {
            // MODIFICADO: Usar <i> para icono
            scanButton.innerHTML = '<i class="icon-spinner icon-spin"></i> Escaneando...';
            scanButton.disabled = true;
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets, tools: selectedToolsPayload, advanced_options: advancedScanOptions }),
            });
            const data = await response.json();
            if (response.ok) {
                currentJobId = data.job_id;
                jobIdDisplay.textContent = currentJobId;
                logToTerminal(`Escaneo iniciado con Job ID: ${currentJobId}`, "success");
                localStorage.setItem('currentJobId', currentJobId);
                clearTimeout(statusPollInterval);
                refreshStatus(currentJobId, true);
                loadJobs();
            } else {
                logToTerminal(`Error al iniciar escaneo (HTTP ${response.status}): ${data.error || 'Error desconocido'}`, "error");
                if (jobInfoPanel) jobInfoPanel.style.display = 'none';
                currentJobInfoDiv.style.display = 'none';
                if (scanButton) {
                    // MODIFICADO: Usar <i> para icono
                    scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo';
                    scanButton.disabled = false;
                }
            }
        } catch (error) {
            logToTerminal(`Error de red al iniciar escaneo: ${error.message || error}`, "error");
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            currentJobInfoDiv.style.display = 'none';
            if (scanButton) {
                // MODIFICADO: Usar <i> para icono
                scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo';
                scanButton.disabled = false;
            }
        }
    }

    if (scanButton) scanButton.onclick = startScan;
    if (refreshButton) refreshButton.onclick = () => {
        if (currentJobId) refreshStatus(currentJobId);
        else logToTerminal("No hay un trabajo activo para refrescar.", "info");
    };

    async function refreshStatus(jobIdToRefresh = null, initialCall = false) {
        const effectiveJobId = jobIdToRefresh || currentJobId;
        if (!effectiveJobId) {
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            currentJobInfoDiv.style.display = 'none';
            cancelJobButton.style.display = 'none';
            downloadJobZipLink.style.display = 'none';
            downloadJobZipLink.classList.add('disabled');
            return;
        }

        if (initialCall) {
            jobIdDisplay.textContent = effectiveJobId;
            if (jobInfoPanel) jobInfoPanel.style.display = 'block';
            currentJobInfoDiv.style.display = 'block';
            cancelJobButton.style.display = 'inline-block';
            downloadJobZipLink.style.display = 'none';
            downloadJobZipLink.classList.add('disabled');
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/status/${effectiveJobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    logToTerminal(`Job ID ${effectiveJobId} no encontrado.`, "warn");
                    if (effectiveJobId === currentJobId) {
                        localStorage.removeItem('currentJobId');
                        currentJobId = null;
                        if (jobInfoPanel) jobInfoPanel.style.display = 'none';
                        currentJobInfoDiv.style.display = 'none';
                        clearTimeout(statusPollInterval);
                        if (scanButton) {
                            // MODIFICADO: Usar <i> para icono
                            scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo';
                            scanButton.disabled = false;
                        }
                        if (jobStatusBadge) { // MODIFICADO: Limpiar badge
                            jobStatusBadge.textContent = 'N/A';
                            jobStatusBadge.className = 'status-badge status-unknown';
                        }
                        overallProgressBar.style.width = `0%`;
                        overallProgressBar.setAttribute('aria-valuenow', 0);
                        overallProgressBar.textContent = `0%`;
                    }
                } else {
                    const errorData = await response.json().catch(() => ({ error: "Error desconocido al obtener estado." }));
                    logToTerminal(`Error al obtener estado (HTTP ${response.status}): ${errorData.error}`, "error");
                }
                return;
            }

            const data = await response.json();
            jobIdDisplay.textContent = data.job_id;
            // MODIFICADO: Usar jobStatusBadge
            if (jobStatusBadge) {
                jobStatusBadge.textContent = data.status;
                jobStatusBadge.className = `status-badge status-${data.status.toLowerCase()}`;
            } else if (jobStatusDisplay) { // Fallback si el badge no existe
                jobStatusDisplay.textContent = data.status;
            }

            const progress = Math.round(data.overall_progress || 0);
            overallProgressBar.style.width = `${progress}%`;
            overallProgressBar.setAttribute('aria-valuenow', progress); // NUEVO: Accesibilidad
            overallProgressBar.textContent = `${progress}%`;
            if (jobInfoPanel && jobInfoPanel.style.display === 'none') jobInfoPanel.style.display = 'block';
            currentJobInfoDiv.style.display = 'block';

            if (scanOutput.dataset.currentJobLog !== data.job_id && initialCall) {
                scanOutput.innerHTML = '';
                logToTerminal(`Mostrando logs para Job ID: ${data.job_id}`, 'info');
                scanOutput.dataset.currentJobLog = data.job_id;
            }

            if (data.logs && Array.isArray(data.logs)) {
                // ASUNCIÓN: el backend envía solo logs nuevos o el frontend debe manejar la duplicación
                // Esta implementación simple asume que si los logs vienen, son para ser mostrados.
                // Para evitar duplicados si el backend envía todos los logs cada vez, necesitarías
                // llevar un contador de logs ya mostrados para este job_id.
                data.logs.forEach(log => {
                    logToTerminal(log.message, log.type || 'info', log.is_html || false);
                });
            }

            if (data.status === 'COMPLETED' || data.status === 'CANCELLED' || data.status === 'ERROR') {
                cancelJobButton.style.display = 'none';
                if (data.zip_path) {
                    downloadJobZipLink.href = `${SCRIPT_ROOT}${data.zip_path}`;
                    downloadJobZipLink.style.display = 'inline-block';
                    downloadJobZipLink.classList.remove('disabled');
                }
                if (effectiveJobId === currentJobId) {
                    if (scanButton) {
                        // MODIFICADO: Usar <i> para icono
                        scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo';
                        scanButton.disabled = false;
                    }
                }
                clearTimeout(statusPollInterval);
                loadJobs();
            } else {
                cancelJobButton.style.display = 'inline-block';
                downloadJobZipLink.style.display = 'none';
                downloadJobZipLink.classList.add('disabled');
                clearTimeout(statusPollInterval);
                statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 5000);
            }

        } catch (error) {
            logToTerminal(`Error de red al obtener estado: ${error.message || error}`, "error");
            clearTimeout(statusPollInterval);
            statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 10000); // Reintentar más tarde
        }
    }

    async function cancelScan() {
        const jobIdToCancel = currentJobId || jobIdDisplay.textContent;
        if (!jobIdToCancel || jobIdToCancel === 'Generando...') {
            logToTerminal("No hay un trabajo específico activo para cancelar.", "warn");
            return;
        }
        // NUEVO: Usar un modal de confirmación más estilizado si es posible, sino confirm es OK
        if (!confirm(`¿Está seguro de que desea cancelar el trabajo ${jobIdToCancel}?`)) {
            return;
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/cancel/${jobIdToCancel}`, { method: 'POST' });
            const data = await response.json();
            if (response.ok) {
                logToTerminal(`Solicitud de cancelación enviada para el trabajo ${jobIdToCancel}.`, "info");
                if (jobStatusBadge) { // MODIFICADO: Actualizar badge
                    jobStatusBadge.textContent = "Cancelando...";
                    jobStatusBadge.className = 'status-badge status-cancelling'; // Clase para estilo
                } else if (jobStatusDisplay) {
                    jobStatusDisplay.textContent = "Cancelando...";
                }
                cancelJobButton.style.display = 'none';
                clearTimeout(statusPollInterval);
                statusPollInterval = setTimeout(() => refreshStatus(jobIdToCancel), 2000);
            } else {
                logToTerminal(`Error al cancelar escaneo (HTTP ${response.status}): ${data.error || 'Error desconocido'}`, "error");
            }
        } catch (error) {
            logToTerminal(`Error de red al cancelar escaneo: ${error.message || error}`, "error");
        }
    }
    if (cancelJobButton) cancelJobButton.onclick = cancelScan;

    async function loadJobs() {
        if (!jobsListArea) return; // Si no existe el área, no hacer nada
        jobsListArea.innerHTML = '<li class="loading-placeholder"><i class="icon-spinner icon-spin"></i> Cargando historial...</li>';
        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/jobs`);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            const jobs = await response.json();

            jobsListArea.innerHTML = '';
            if (jobs.length === 0) {
                jobsListArea.innerHTML = '<li class="empty-placeholder">No hay trabajos anteriores.</li>';
                return;
            }
            jobs.forEach(job => {
                const li = document.createElement('li');
                li.classList.add('job-card', `status-${job.status.toLowerCase()}`); // Clase de estado para estilizar tarjeta
                if (job.id === currentJobId) {
                    li.classList.add('active-job-card'); // NUEVO: para resaltar el job actual en la lista
                }

                let targetsDisplay = Array.isArray(job.targets) ? job.targets.join(', ') : (job.targets || 'N/A');
                if (targetsDisplay.length > 35) targetsDisplay = targetsDisplay.substring(0, 32) + '...';

                // MODIFICADO: Usar clases de icono para el estado
                let statusIconClass = 'icon-question-circle';
                if (job.status === 'COMPLETED') statusIconClass = 'icon-check-circle-green'; // Verde para completado
                else if (job.status === 'RUNNING') statusIconClass = 'icon-spinner icon-spin blue'; // Azul para corriendo
                else if (job.status === 'ERROR') statusIconClass = 'icon-times-circle-red'; // Rojo para error
                else if (job.status === 'CANCELLED') statusIconClass = 'icon-ban grey'; // Gris para cancelado
                else if (job.status === 'PENDING') statusIconClass = 'icon-clock orange'; // Naranja para pendiente

                li.innerHTML = `
                    <div class="job-card-header">
                        <span class="job-id">ID: ${job.id}</span>
                        <span class="job-status job-status-${job.status.toLowerCase()}">
                            <i class="${statusIconClass}"></i> ${job.status}
                        </span>
                    </div>
                    <div class="job-card-body">
                        <p class="job-targets" title="${Array.isArray(job.targets) ? job.targets.join(', ') : (job.targets || 'N/A')}">
                            <strong><i class="icon-target"></i> Objetivos:</strong> ${targetsDisplay}
                        </p>
                        <p class="job-timestamp">
                            <strong><i class="icon-calendar"></i> Fecha:</strong> ${job.timestamp ? new Date(job.timestamp).toLocaleString() : 'N/A'}
                        </p>
                    </div>
                    <div class="job-card-actions">
                        <button class="button-secondary view-details-btn" data-job-id="${job.id}">
                            <i class="icon-eye"></i> Ver Detalles
                        </button>
                        ${job.zip_path ? `<a href="${SCRIPT_ROOT}${job.zip_path}" class="button-success download-zip-btn" target="_blank">
                                            <i class="icon-download"></i> Descargar ZIP
                                          </a>` :
                        `<button class="button-disabled download-zip-btn" disabled title="Resultados no disponibles para descarga">
                                             <i class="icon-download"></i> Descargar ZIP
                                           </button>`}
                    </div>`;
                li.querySelector('.view-details-btn').onclick = (e) => {
                    e.stopPropagation();
                    viewJobDetails(job.id);
                };
                // NUEVO: Permitir click en toda la tarjeta para ver detalles
                li.onclick = () => viewJobDetails(job.id);

                jobsListArea.appendChild(li);
            });
        } catch (error) {
            logToTerminal(`Error al cargar historial de trabajos: ${error.message || error}`, "error");
            jobsListArea.innerHTML = '<li class="error-message">Error al cargar trabajos.</li>';
        }
    }

    function viewJobDetails(jobId) {
        logToTerminal(`Cargando detalles para el trabajo ${jobId}...`, "info");
        currentJobId = jobId;
        localStorage.setItem('currentJobId', jobId);
        clearTimeout(statusPollInterval);
        scanOutput.innerHTML = '';
        scanOutput.dataset.currentJobLog = jobId;
        // logEntryCounter = 0; // No es necesario si no hay animación secuencial de logs
        refreshStatus(jobId, true);

        // NUEVO: Resaltar el job card activo
        document.querySelectorAll('.job-card.active-job-card').forEach(card => card.classList.remove('active-job-card'));
        const activeCard = Array.from(jobsListArea.querySelectorAll('.job-card')).find(card => card.querySelector('.view-details-btn')?.dataset.jobId === jobId);
        if (activeCard) activeCard.classList.add('active-job-card');

        const terminalPanel = document.getElementById('terminal-panel'); // Asumiendo que este es el ID correcto
        if (terminalPanel) {
            terminalPanel.scrollIntoView({ behavior: 'smooth' });
        } else { // Fallback si el panel no existe, ir a la pestaña de Output
            const outputTabButton = document.querySelector('.tab-link[onclick*="OutputTab"]');
            if (outputTabButton) outputTabButton.click();
        }
    }

    if (importTargetsButton && importTargetsFile) {
        importTargetsButton.onclick = () => importTargetsFile.click();
        importTargetsFile.onchange = (event) => {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    targetsTextarea.value = e.target.result;
                    logToTerminal(`Targets importados desde ${file.name}`, 'success'); // MODIFICADO: success type
                    updateTargetsCount(); // NUEVO
                };
                reader.readAsText(file);
                importTargetsFile.value = '';
            }
        };
    }

    if (copyLogButton) {
        copyLogButton.onclick = () => {
            if (navigator.clipboard && scanOutput) {
                // MODIFICADO: Copiar solo el texto, sin timestamps/iconos de la UI si es posible.
                // Si se quieren timestamps, extraerlos del DOM.
                let logText = "";
                scanOutput.querySelectorAll('.log-entry').forEach(entry => {
                    const timestamp = entry.querySelector('.log-timestamp')?.textContent || "";
                    const message = entry.querySelector('.log-message-content')?.textContent || "";
                    logText += `${timestamp} ${message}\n`;
                });

                navigator.clipboard.writeText(logText.trim())
                    .then(() => logToTerminal("Log copiado al portapapeles.", "success"))
                    .catch(err => logToTerminal("Error al copiar log: " + err, "error"));
            } else {
                logToTerminal("La API de portapapeles no está disponible en este navegador.", "warn");
            }
        };
    }
    if (downloadLogButton && scanOutput) {
        downloadLogButton.onclick = () => {
            let logData = ""; // MODIFICADO: similar a copyLogButton
            scanOutput.querySelectorAll('.log-entry').forEach(entry => {
                const timestamp = entry.querySelector('.log-timestamp')?.textContent || "";
                const message = entry.querySelector('.log-message-content')?.textContent || "";
                logData += `${timestamp} ${message}\n`;
            });
            logData = logData.trim();

            const blob = new Blob([logData], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const timestampFile = new Date().toISOString().replace(/[:.]/g, '-');
            a.download = `panthera_scan_log_${currentJobId || 'session'}_${timestampFile}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            logToTerminal("Log preparado para descarga.", "success");
        };
    }

    window.openTab = function (evt, tabName) {
        let i, tabcontent, tablinks;
        tabcontent = document.getElementsByClassName("tab-content");
        for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].style.display = "none"; // MODIFICADO: Usar style.display para compatibilidad con .active
            tabcontent[i].classList.remove("active");
        }
        tablinks = document.getElementsByClassName("tab-link");
        for (i = 0; i < tablinks.length; i++) {
            tablinks[i].classList.remove("active");
        }
        const activeTabContent = document.getElementById(tabName);
        if (activeTabContent) {
            activeTabContent.style.display = "block"; // MODIFICADO
            activeTabContent.classList.add("active");
        }
        if (evt && evt.currentTarget) {
            evt.currentTarget.classList.add("active");
        }
    }
    const firstTabButton = document.querySelector('.tabs .tab-link');
    if (firstTabButton) {
        // Simular un evento de click para que openTab se ejecute correctamente
        // Esto es mejor que llamar a firstTabButton.click() directamente si hay manejadores de eventos complejos
        const mockEvent = { currentTarget: firstTabButton };
        const tabName = firstTabButton.getAttribute('onclick').match(/openTab\(event, ['"](.*?)['"]\)/)[1];
        openTab(mockEvent, tabName);
    }


    // Inicialización
    fetchAppConfig().then(() => {
        loadJobs();
        updateTargetsCount(); // NUEVO: Contar targets al inicio
        if (currentJobId) {
            viewJobDetails(currentJobId);
        } else {
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            currentJobInfoDiv.style.display = 'none';
            // Seleccionar la primera pestaña si no hay job actual
            if (firstTabButton && !currentJobId) {
                const mockEvent = { currentTarget: firstTabButton };
                const tabName = firstTabButton.getAttribute('onclick').match(/openTab\(event, ['"](.*?)['"]\)/)[1];
                openTab(mockEvent, tabName);
            }
        }
    });
});