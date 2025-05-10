document.addEventListener('DOMContentLoaded', () => {
    const toolListDiv = document.getElementById('toolList');
    const scanOutput = document.getElementById('scanOutput');
    const targetsTextarea = document.getElementById('targets');
    const jobIdDisplay = document.getElementById('jobIdDisplay');
    const jobStatusBadge = document.getElementById('jobStatusBadge');
    const overallProgressBar = document.getElementById('overallProgressBar');
    const currentJobInfoDiv = document.getElementById('currentJobInfo');
    const jobInfoPanel = document.getElementById('job-info-panel');
    const cancelJobButton = document.getElementById('cancelJobButton');
    const downloadJobZipLink = document.getElementById('downloadJobZip');
    const jobsListArea = document.getElementById('jobsListArea');

    const importTargetsButton = document.getElementById('importTargetsButton');
    const importTargetsFile = document.getElementById('importTargetsFile');
    const clearTargetsButton = document.getElementById('clearTargetsButton');
    const targetsCountDisplay = document.getElementById('targetsCount');

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

    let displayedLogCount = 0;
    let currentJobIdForLogs = null;


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
        if (!scanOutput) {
            console.warn("Elemento scanOutput no encontrado. Mensaje de log:", message);
            return;
        }
        const entry = document.createElement('div');
        entry.classList.add('log-entry', `log-type-${type.toLowerCase()}`);

        const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        let iconClass = 'icon-info-circle'; // Default
        if (type === 'error') iconClass = 'icon-times-circle';
        else if (type === 'warn') iconClass = 'icon-exclamation-triangle';
        else if (type === 'success') iconClass = 'icon-check-circle';
        else if (type === 'command') iconClass = 'icon-terminal';

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
            if (toolListDiv) populateToolSelection();
            if (document.querySelector('.scan-profiles-buttons')) populateScanProfiles();
        } catch (error) {
            logToTerminal(`Error al cargar la configuración de la aplicación: ${error}`, 'error');
            if (toolListDiv) toolListDiv.innerHTML = '<p class="error-message">Error al cargar herramientas. Intente recargar la página.</p>';
        }
    }

    function populateScanProfiles() {
        const profilesContainer = document.querySelector('.scan-profiles-buttons');
        if (!profilesContainer || !appConfig.profiles) return;
        profilesContainer.innerHTML = '';

        Object.keys(appConfig.profiles).forEach(profileName => {
            const profile = appConfig.profiles[profileName];
            const button = document.createElement('button');
            button.className = 'button-profile';
            button.innerHTML = `<i class="${profile.icon_class || 'icon-profile'}"></i> <span>${profileName}</span>`;
            button.title = profile.description || profileName;
            button.dataset.profileName = profileName;
            button.onclick = () => applyScanProfile(profileName);
            profilesContainer.appendChild(button);
        });
        const deselectAllButton = document.createElement('button');
        deselectAllButton.className = 'button-profile-deselect';
        deselectAllButton.innerHTML = '<i class="icon-square-o"></i> <span>Desmarcar Todas</span>';
        deselectAllButton.onclick = () => deselectAllTools();
        profilesContainer.appendChild(deselectAllButton);
    }

    function populateToolSelection() {
        if (!toolListDiv || !appConfig.tools || !appConfig.phases) {
            console.error("populateToolSelection: Elementos DOM o configuración faltante.");
            return;
        }
        toolListDiv.innerHTML = '';
        let uniqueIdCounter = 0;

        const toolsByPhaseAndCategory = {};
        for (const toolKey in appConfig.tools) {
            const tool = appConfig.tools[toolKey];
            const phaseKey = tool.phase; // e.g., "reconnaissance_infra_web"
            const categoryKey = tool.category; // e.g., "Asset Discovery"

            if (!toolsByPhaseAndCategory[phaseKey]) {
                toolsByPhaseAndCategory[phaseKey] = {
                    meta: appConfig.phases[phaseKey] || { name: phaseKey, order: 99, icon_class: 'icon-question-circle' },
                    categories: {}
                };
            }
            if (!toolsByPhaseAndCategory[phaseKey].categories[categoryKey]) {
                toolsByPhaseAndCategory[phaseKey].categories[categoryKey] = {
                    display_name: tool.category_display_name || categoryKey,
                    icon_class: tool.category_icon_class || 'icon-folder',
                    tools: []
                };
            }
            toolsByPhaseAndCategory[phaseKey].categories[categoryKey].tools.push({ ...tool, id: toolKey });
        }

        const sortedPhaseKeys = Object.keys(toolsByPhaseAndCategory).sort((a, b) => {
            const orderA = toolsByPhaseAndCategory[a].meta.order || 99;
            const orderB = toolsByPhaseAndCategory[b].meta.order || 99;
            return orderA - orderB;
        });


        for (const phaseKey of sortedPhaseKeys) {
            const phaseData = toolsByPhaseAndCategory[phaseKey];
            const phaseId = `phase-toggle-${uniqueIdCounter++}`;
            const phaseDiv = document.createElement('div');
            phaseDiv.className = 'pentest-phase';

            const phaseDisplayName = phaseData.meta.name || phaseKey;
            const phaseIconClass = phaseData.meta.icon_class || 'icon-layer-group';

            const phaseHeader = document.createElement('div');
            phaseHeader.className = 'pentest-phase-header';
            phaseHeader.innerHTML = `
                <label class="toggle-switch">
                    <input type="checkbox" id="${phaseId}" data-type="phase">
                    <span class="slider"></span>
                </label>
                <h4><i class="${phaseIconClass}"></i> ${phaseDisplayName}</h4>`;
            phaseDiv.appendChild(phaseHeader);

            for (const categoryKey in phaseData.categories) {
                const categoryData = phaseData.categories[categoryKey];
                const categoryId = `category-toggle-${uniqueIdCounter++}`;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'tool-category';

                const categoryDisplayName = categoryData.display_name;
                const categoryIconClass = categoryData.icon_class;

                const categoryHeader = document.createElement('div');
                categoryHeader.className = 'tool-category-header';
                categoryHeader.innerHTML = `
                    <label class="toggle-switch">
                        <input type="checkbox" id="${categoryId}" class="tool-category-checkbox" data-phase-parent-id="${phaseId}" data-type="category">
                        <span class="slider"></span>
                    </label>
                    <h5><i class="${categoryIconClass}"></i> ${categoryDisplayName}</h5>
                    <span class="accordion-arrow"><i class="icon-chevron-down"></i></span>`;

                const toolItemsContainer = document.createElement('div');
                toolItemsContainer.className = 'tool-items-container'; // Inicialmente colapsado

                categoryHeader.onclick = (e) => {
                    if (e.target.type === 'checkbox' || e.target.classList.contains('slider') || e.target.closest('.toggle-switch')) return;

                    toolItemsContainer.classList.toggle('expanded');
                    const arrowIcon = categoryHeader.querySelector('.accordion-arrow i');
                    if (arrowIcon) {
                        arrowIcon.className = toolItemsContainer.classList.contains('expanded') ? 'icon-chevron-up' : 'icon-chevron-down';
                    }
                };
                categoryDiv.appendChild(categoryHeader);

                categoryData.tools.forEach(tool => {
                    const toolItemId = `tool-toggle-${tool.id}-${uniqueIdCounter++}`;
                    const toolItemDiv = document.createElement('div');
                    toolItemDiv.className = 'tool-item';
                    let cliParamsHtml = '';
                    if (tool.cli_params_config && tool.cli_params_config.length > 0) {
                        cliParamsHtml += `<div class="tool-cli-params-group" id="cli-group-${tool.id}" style="display:none;"><h6><i class="icon-sliders-h"></i> Parámetros Adicionales:</h6>`;
                        tool.cli_params_config.forEach(paramConf => {
                            cliParamsHtml += `<div class="cli-param-row">
                                <label for="cli-${tool.id}-${paramConf.name}" title="${paramConf.description || ''}">${paramConf.label}:</label>`;
                            if (paramConf.type === 'select') {
                                cliParamsHtml += `<select id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" title="${paramConf.description || ''}">`;
                                (paramConf.options || []).forEach(opt => {
                                    const value = typeof opt === 'string' ? opt : opt.value; // Si options es [{value:'v', label:'l'}] o ['v1','v2']
                                    const label = typeof opt === 'string' ? opt : opt.label;
                                    cliParamsHtml += `<option value="${value}" ${value === paramConf.default ? 'selected' : ''}>${label}</option>`;
                                });
                                cliParamsHtml += `</select>`;
                            } else if (paramConf.type === 'password') {
                                cliParamsHtml += `<input type="password" id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" placeholder="${paramConf.placeholder || ''}" value="${paramConf.default || ''}" title="${paramConf.description || ''}">`;
                            }
                            else {
                                cliParamsHtml += `<input type="${paramConf.type || 'text'}" id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" placeholder="${paramConf.placeholder || ''}" value="${paramConf.default || ''}" title="${paramConf.description || ''}">`;
                            }
                            cliParamsHtml += `</div>`;
                        });
                        cliParamsHtml += `</div>`;
                    }
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
                        <div class="tool-details" style="display:none;"> ${cliParamsHtml}</div>`;

                    const toolCheckboxInput = toolItemDiv.querySelector('.tool-item-checkbox');
                    if (toolCheckboxInput) {
                        toolCheckboxInput.addEventListener('change', (e) => {
                            const toolDetails = toolItemDiv.querySelector('.tool-details');
                            if (toolDetails) toolDetails.style.display = e.target.checked ? 'block' : 'none';
                        });
                        if (tool.default_enabled) {
                            const toolDetails = toolItemDiv.querySelector('.tool-details');
                            if (toolDetails) toolDetails.style.display = 'block';
                        }
                    }
                    toolItemsContainer.appendChild(toolItemDiv);
                });
                categoryDiv.appendChild(toolItemsContainer);
                phaseDiv.appendChild(categoryDiv);
            }
            toolListDiv.appendChild(phaseDiv);
        }
        addCheckboxEventListeners();
        updateAllParentCheckboxes(); // Asegurar que los padres reflejen el estado inicial de los hijos
        document.querySelectorAll('.tool-items-container').forEach(container => {
            container.classList.remove('expanded');
            const header = container.previousElementSibling; // El .tool-category-header
            if (header) {
                const arrowIcon = header.querySelector('.accordion-arrow i');
                if (arrowIcon) arrowIcon.className = 'icon-chevron-down';
            }
        });
    }

    function addCheckboxEventListeners() {
        if (!toolListDiv) return;
        toolListDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', handleCheckboxChange);
        });
    }

    function handleCheckboxChange(event) {
        const checkbox = event.target;
        const type = checkbox.dataset.type;

        if (type === 'phase') {
            const phaseId = checkbox.id;
            if (toolListDiv) {
                toolListDiv.querySelectorAll(`.tool-category-checkbox[data-phase-parent-id="${phaseId}"]`).forEach(catCb => {
                    catCb.checked = checkbox.checked;
                    catCb.indeterminate = false;
                    toggleChildren(catCb, checkbox.checked); // Propagar a herramientas
                });
            }
        } else if (type === 'category') {
            toggleChildren(checkbox, checkbox.checked);
            updateParentCheckboxState(checkbox.dataset.phaseParentId); // Actualizar fase padre
        } else if (type === 'tool') {
            updateParentCheckboxState(checkbox.dataset.categoryParentId); // Actualizar categoría padre
        }
    }

    function toggleChildren(parentCheckbox, isChecked) {
        const parentType = parentCheckbox.dataset.type;
        let childrenSelector = '';
        if (parentType === 'category') { // Solo las categorías tienen herramientas como hijos directos en esta lógica
            childrenSelector = `.tool-item-checkbox[data-category-parent-id="${parentCheckbox.id}"]`;
        }

        if (childrenSelector) {
            const categoryDiv = parentCheckbox.closest('.tool-category'); // El contenedor de la categoría
            if (!categoryDiv) return;

            categoryDiv.querySelectorAll(childrenSelector).forEach(childCb => {
                childCb.checked = isChecked;
                childCb.indeterminate = false; // Los hijos directos no son indeterminados
                const toolItem = childCb.closest('.tool-item');
                if (toolItem) {
                    const toolDetailsDiv = toolItem.querySelector('.tool-details');
                    if (toolDetailsDiv) {
                        toolDetailsDiv.style.display = isChecked ? 'block' : 'none';
                    }
                }
            });
        }
    }

    function updateParentCheckboxState(parentId) {
        if (!parentId) return;
        const parentCheckbox = document.getElementById(parentId);
        if (!parentCheckbox) return;

        const parentType = parentCheckbox.dataset.type;
        let childrenCheckboxesNodeList;

        if (parentType === 'phase') {
            childrenCheckboxesNodeList = toolListDiv ? toolListDiv.querySelectorAll(`.tool-category-checkbox[data-phase-parent-id="${parentId}"]`) : [];
        } else if (parentType === 'category') {
            const categoryDiv = parentCheckbox.closest('.tool-category');
            if (!categoryDiv) return;
            childrenCheckboxesNodeList = categoryDiv.querySelectorAll(`.tool-item-checkbox[data-category-parent-id="${parentId}"]`);
        } else {
            return; // No es un padre que necesite actualización de esta manera
        }

        const childrenArray = Array.from(childrenCheckboxesNodeList);
        if (childrenArray.length === 0) { // Si no hay hijos, el estado del padre es simplemente su propio 'checked'
            parentCheckbox.indeterminate = false;
            return;
        }

        const allChecked = childrenArray.every(child => child.checked && !child.indeterminate);
        const someChecked = childrenArray.some(child => child.checked || child.indeterminate);

        parentCheckbox.checked = allChecked;
        parentCheckbox.indeterminate = !allChecked && someChecked;

        if (parentType === 'category' && parentCheckbox.dataset.phaseParentId) {
            updateParentCheckboxState(parentCheckbox.dataset.phaseParentId);
        }
    }

    function updateAllParentCheckboxes() {
        if (!toolListDiv) return;
        toolListDiv.querySelectorAll('.tool-item-checkbox').forEach(toolCb => {
            const toolItem = toolCb.closest('.tool-item');
            if (toolItem) {
                const toolDetailsDiv = toolItem.querySelector('.tool-details');
                if (toolDetailsDiv) {
                    toolDetailsDiv.style.display = toolCb.checked ? 'block' : 'none';
                }
            }
        });
        toolListDiv.querySelectorAll('.tool-category-checkbox').forEach(catCb => {
            updateParentCheckboxState(catCb.id); // Esto actualizará la categoría y luego su fase padre
        });
    }


    window.applyScanProfile = function (profileName) {
        deselectAllTools(); // Primero deselecciona todo
        const profile = appConfig.profiles[profileName];
        if (profile && profile.tools && toolListDiv) {
            profile.tools.forEach(toolId => {
                const toolCheckbox = toolListDiv.querySelector(`input[name="selected_tools"][value="${toolId}"]`);
                if (toolCheckbox) {
                    toolCheckbox.checked = true;
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
        updateAllParentCheckboxes(); // Actualiza el estado visual de todos los checkboxes y detalles
        document.querySelectorAll('.button-profile').forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.profileName === profileName) {
                btn.classList.add('active');
            }
        });
    }

    window.deselectAllTools = function () {
        if (toolListDiv) {
            toolListDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                checkbox.checked = false;
                checkbox.indeterminate = false;
                if (checkbox.dataset.type === 'tool') { // Ocultar detalles de herramientas
                    const toolItem = checkbox.closest('.tool-item');
                    if (toolItem) {
                        const toolDetailsDiv = toolItem.querySelector('.tool-details');
                        if (toolDetailsDiv) toolDetailsDiv.style.display = 'none';
                    }
                }
            });
        }
        document.querySelectorAll('.button-profile.active').forEach(btn => btn.classList.remove('active'));
        logToTerminal('Todas las herramientas deseleccionadas.', 'info');
    }

    async function startScan() {
        const targets = targetsTextarea && targetsTextarea.value.trim().split('\n').filter(t => t.trim() !== '') || [];
        if (targets.length === 0) {
            logToTerminal("Por favor, ingrese al menos un objetivo.", "error");
            if (targetsTextarea) targetsTextarea.focus();
            return;
        }

        const selectedToolsPayload = [];
        document.querySelectorAll('input[name="selected_tools"]:checked').forEach(cb => {
            const toolId = cb.value;
            const toolConfig = appConfig.tools[toolId]; // Obtener la config completa de la herramienta
            let params = {};
            if (toolConfig && toolConfig.cli_params_config) {
                toolConfig.cli_params_config.forEach(pConf => {
                    const inputField = document.getElementById(`cli-${toolId}-${pConf.name}`);
                    if (inputField && inputField.value.trim() !== '') { // Usar valor del input si no está vacío
                        params[pConf.name] = inputField.value;
                    } else if (pConf.default && pConf.default.trim() !== '') { // Usar default si input está vacío pero default no
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
        const advancedScanOptions = { // Recoger opciones avanzadas si existen
            customScanTime: document.getElementById('customScanTime')?.value || null,
            followRedirects: document.getElementById('followRedirects')?.checked || false,
            scanIntensity: document.getElementById('scanIntensity')?.value || 'normal',
            tool_timeout: document.getElementById('toolTimeout')?.value || null, // Nuevo campo
        };

        logToTerminal(`Iniciando escaneo para objetivo(s): ${targets.join(', ')}...`, 'command');
        if (jobInfoPanel) jobInfoPanel.style.display = 'block';
        if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'block';
        if (jobIdDisplay) jobIdDisplay.textContent = 'Generando...';
        if (jobStatusBadge) {
            jobStatusBadge.textContent = 'Iniciando';
            jobStatusBadge.className = 'status-badge status-pending';
        }
        if (overallProgressBar) {
            overallProgressBar.style.width = '0%';
            overallProgressBar.setAttribute('aria-valuenow', '0');
            overallProgressBar.textContent = '0%';
        }
        if (cancelJobButton) cancelJobButton.style.display = 'inline-block'; // Mostrar botón de cancelar
        if (downloadJobZipLink) { // Ocultar y deshabilitar link de descarga
            downloadJobZipLink.style.display = 'none';
            downloadJobZipLink.classList.add('disabled');
            downloadJobZipLink.href = '#';
        }
        if (scanButton) {
            scanButton.innerHTML = '<i class="icon-spinner icon-spin"></i> Escaneando...';
            scanButton.disabled = true;
        }
        if (scanOutput) scanOutput.innerHTML = ''; // Limpiar logs anteriores
        displayedLogCount = 0;
        currentJobIdForLogs = null;

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targets, tools: selectedToolsPayload, advanced_options: advancedScanOptions }),
            });
            const data = await response.json();
            if (response.ok && data.job_id) {
                currentJobId = data.job_id;
                currentJobIdForLogs = data.job_id;
                if (jobIdDisplay) jobIdDisplay.textContent = currentJobId;
                logToTerminal(`Escaneo iniciado con Job ID: ${currentJobId}`, "success");
                localStorage.setItem('currentJobId', currentJobId);
                clearTimeout(statusPollInterval);
                refreshStatus(currentJobId, true); // Iniciar polling
                if (jobsListArea) loadJobs(); // Actualizar lista de jobs
            } else {
                logToTerminal(`Error al iniciar escaneo (HTTP ${response.status}): ${data.error || 'Error desconocido del servidor'}`, "error");
                if (jobInfoPanel) jobInfoPanel.style.display = 'none';
                if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
                if (scanButton) {
                    scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo';
                    scanButton.disabled = false;
                }
            }
        } catch (error) {
            logToTerminal(`Error de red al iniciar escaneo: ${error.message || error}`, "error");
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
            if (scanButton) {
                scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo';
                scanButton.disabled = false;
            }
        }
    }

    async function refreshStatus(jobIdToRefresh = null, initialCall = false) {
        const effectiveJobId = jobIdToRefresh || currentJobId;
        if (!effectiveJobId) { // No hay job activo o seleccionado
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
            if (cancelJobButton) cancelJobButton.style.display = 'none';
            if (downloadJobZipLink) {
                downloadJobZipLink.style.display = 'none';
                downloadJobZipLink.classList.add('disabled');
            }
            return;
        }

        if (initialCall) { // Mostrar panel de info del job si es la primera llamada para este job
            if (jobIdDisplay) jobIdDisplay.textContent = effectiveJobId;
            if (jobInfoPanel) jobInfoPanel.style.display = 'block';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'block';
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/status/${effectiveJobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    logToTerminal(`Job ID ${effectiveJobId} no encontrado. Pudo haber sido purgado o es inválido.`, "warn");
                    if (effectiveJobId === currentJobId) { // Si era el job activo, limpiar
                        localStorage.removeItem('currentJobId');
                        currentJobId = null; currentJobIdForLogs = null; displayedLogCount = 0;
                        if (jobInfoPanel) jobInfoPanel.style.display = 'none';
                        if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
                        clearTimeout(statusPollInterval);
                        if (scanButton) { scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo'; scanButton.disabled = false; }
                        if (jobStatusBadge) { jobStatusBadge.textContent = 'N/A'; jobStatusBadge.className = 'status-badge status-unknown'; }
                        if (overallProgressBar) { overallProgressBar.style.width = `0%`; overallProgressBar.setAttribute('aria-valuenow', 0); overallProgressBar.textContent = `0%`; }
                    }
                } else {
                    const errorData = await response.json().catch(() => ({ error: "Error desconocido al obtener estado." }));
                    logToTerminal(`Error al obtener estado del Job ${effectiveJobId} (HTTP ${response.status}): ${errorData.error || 'Error de servidor'}`, "error");
                }
                return; // No continuar si hay error
            }

            const data = await response.json();
            if (!data || !data.job_id) {
                logToTerminal(`Respuesta inválida del servidor para el estado del Job ${effectiveJobId}.`, "error");
                return;
            }

            if (jobIdDisplay) jobIdDisplay.textContent = data.job_id; // Actualizar por si acaso
            if (jobStatusBadge) {
                jobStatusBadge.textContent = data.status || 'Desconocido';
                jobStatusBadge.className = `status-badge status-${(data.status || 'unknown').toLowerCase().replace(/_/g, '-')}`;
            }

            const progress = Math.round(data.overall_progress || 0);
            if (overallProgressBar) {
                overallProgressBar.style.width = `${progress}%`;
                overallProgressBar.setAttribute('aria-valuenow', progress);
                overallProgressBar.textContent = `${progress}%`;
            }
            if (jobInfoPanel && jobInfoPanel.style.display === 'none') jobInfoPanel.style.display = 'block';
            if (currentJobInfoDiv && currentJobInfoDiv.style.display === 'none') currentJobInfoDiv.style.display = 'block';


            if (currentJobIdForLogs !== data.job_id || initialCall) { // Si cambiamos de job o es la primera carga de este job
                if (scanOutput) scanOutput.innerHTML = ''; // Limpiar logs anteriores
                displayedLogCount = 0;
                if (currentJobIdForLogs !== data.job_id || (initialCall && (!scanOutput || scanOutput.innerHTML === ''))) {
                    logToTerminal(`Mostrando logs para Job ID: ${data.job_id}`, 'info');
                }
                currentJobIdForLogs = data.job_id;
            }

            if (data.logs && Array.isArray(data.logs)) {
                const newLogs = data.logs.slice(displayedLogCount); // Solo procesar logs nuevos
                newLogs.forEach(log => {
                    let logDisplayType = (log.level || 'info').toLowerCase(); // Usar log.level para determinar el tipo de UI
                    const validDisplayTypes = ['info', 'error', 'warn', 'success', 'command'];
                    if (!validDisplayTypes.includes(logDisplayType)) {
                        logDisplayType = (logDisplayType === 'debug') ? 'info' : 'info'; // Mapear debug o desconocidos a info
                    }
                    logToTerminal(log.message, logDisplayType, log.is_html || false);
                });
                displayedLogCount = data.logs.length; // Actualizar contador de logs mostrados
            }

            const terminalStates = ['COMPLETED', 'CANCELLED', 'ERROR', 'COMPLETED_WITH_ERRORS']; // Estados que detienen el polling
            if (terminalStates.includes(data.status?.toUpperCase())) {
                if (cancelJobButton) cancelJobButton.style.display = 'none';
                if (data.zip_path && downloadJobZipLink) {
                    downloadJobZipLink.href = `${SCRIPT_ROOT}${data.zip_path}`; // SCRIPT_ROOT para URL correcta
                    downloadJobZipLink.style.display = 'inline-block';
                    downloadJobZipLink.classList.remove('disabled');
                } else if (downloadJobZipLink) {
                    downloadJobZipLink.style.display = 'none';
                    downloadJobZipLink.classList.add('disabled');
                }
                if (effectiveJobId === currentJobId) { // Solo re-habilitar botón si es el job actualmente "activo" en la UI
                    if (scanButton) { scanButton.innerHTML = '<i class="icon-zap"></i> Iniciar Escaneo'; scanButton.disabled = false; }
                }
                clearTimeout(statusPollInterval);
                if (jobsListArea) loadJobs(); // Actualizar lista de jobs al finalizar
            } else { // Job todavía en progreso
                if (cancelJobButton) cancelJobButton.style.display = 'inline-block'; // Asegurar que esté visible
                if (downloadJobZipLink) { // Asegurar que esté oculto y deshabilitado
                    downloadJobZipLink.style.display = 'none';
                    downloadJobZipLink.classList.add('disabled');
                }
                clearTimeout(statusPollInterval); // Limpiar timeout anterior
                statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 3000); // Polling cada 3 segundos
            }

        } catch (error) {
            logToTerminal(`Error de red al obtener estado del Job ${effectiveJobId}: ${error.message || error}`, "error");
            clearTimeout(statusPollInterval); // Limpiar timeout anterior
            statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 7000); // Reintentar más tarde si hay error de red
        }
    }

    async function cancelScan() {
        const jobIdToCancel = currentJobId || (jobIdDisplay ? jobIdDisplay.textContent : null);
        if (!jobIdToCancel || jobIdToCancel === 'Generando...') {
            logToTerminal("No hay un trabajo específico activo para cancelar.", "warn");
            return;
        }
        if (!confirm(`¿Está seguro de que desea cancelar el trabajo ${jobIdToCancel}?`)) {
            return;
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/cancel/${jobIdToCancel}`, { method: 'POST' });
            const data = await response.json(); // Siempre intentar parsear JSON
            if (response.ok) {
                logToTerminal(`Solicitud de cancelación enviada para el trabajo ${jobIdToCancel}. Estado: ${data.message || 'OK'}.`, "info");
                if (jobStatusBadge) {
                    jobStatusBadge.textContent = "Cancelando...";
                    jobStatusBadge.className = 'status-badge status-cancelling';
                }
                if (cancelJobButton) cancelJobButton.style.display = 'none'; // Ocultar botón tras solicitar cancelación
                clearTimeout(statusPollInterval); // Limpiar polling actual
                statusPollInterval = setTimeout(() => refreshStatus(jobIdToCancel), 1500); // Verificar estado pronto
            } else {
                logToTerminal(`Error al cancelar escaneo (HTTP ${response.status}): ${data.error || data.message || 'Error desconocido'}`, "error");
            }
        } catch (error) {
            logToTerminal(`Error de red al cancelar escaneo: ${error.message || error}`, "error");
        }
    }

    async function loadJobs() {
        if (!jobsListArea) return;
        jobsListArea.innerHTML = '<li class="loading-placeholder"><i class="icon-spinner icon-spin"></i> Cargando historial...</li>';
        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/jobs`);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            const jobs = await response.json();
            jobsListArea.innerHTML = ''; // Limpiar placeholder
            if (!jobs || jobs.length === 0) {
                jobsListArea.innerHTML = '<li class="empty-placeholder">No hay trabajos anteriores.</li>';
                return;
            }
            jobs.forEach(job => { // 'job.id' ya es el job_id
                const li = document.createElement('li');
                const statusClass = (job.status || 'unknown').toLowerCase().replace(/_/g, '-');
                li.classList.add('job-card', `status-${statusClass}`);
                if (job.id === currentJobId) { // Marcar el job activo
                    li.classList.add('active-job-card');
                }
                let targetsDisplay = Array.isArray(job.targets) ? job.targets.join(', ') : (job.targets || 'N/A');
                if (targetsDisplay.length > 35) targetsDisplay = targetsDisplay.substring(0, 32) + '...';

                let statusIconClass = 'icon-question-circle'; // Default
                const upperStatus = (job.status || '').toUpperCase();
                if (upperStatus === 'COMPLETED') statusIconClass = 'icon-check-circle-green';
                else if (upperStatus === 'COMPLETED_WITH_ERRORS') statusIconClass = 'icon-check-circle-orange'; // Nuevo estado
                else if (upperStatus === 'RUNNING') statusIconClass = 'icon-spinner icon-spin blue';
                else if (upperStatus === 'ERROR') statusIconClass = 'icon-times-circle-red';
                else if (upperStatus === 'CANCELLED') statusIconClass = 'icon-ban grey';
                else if (upperStatus === 'PENDING' || upperStatus === 'INITIALIZING' || upperStatus === 'REQUEST_CANCEL' || upperStatus === 'CANCELLING') statusIconClass = 'icon-clock orange';


                li.innerHTML = `
                    <div class="job-card-header">
                        <span class="job-id">ID: ${job.id}</span>
                        <span class="job-status job-status-${statusClass}">
                            <i class="${statusIconClass}"></i> ${job.status || 'Desconocido'}
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
                        ${job.zip_path ? `<a href="${SCRIPT_ROOT}${job.zip_path}" class="button-success download-zip-btn" target="_blank" rel="noopener noreferrer">
                                            <i class="icon-download"></i> Descargar ZIP
                                         </a>` :
                        `<button class="button-disabled download-zip-btn" disabled title="Resultados no disponibles para descarga">
                                            <i class="icon-download"></i> Descargar ZIP
                                        </button>`}
                    </div>`;
                const viewDetailsBtn = li.querySelector('.view-details-btn');
                if (viewDetailsBtn) {
                    viewDetailsBtn.onclick = (e) => {
                        e.stopPropagation(); // Evitar que el click en el botón active el click en el li
                        viewJobDetails(job.id);
                    };
                }
                li.onclick = () => viewJobDetails(job.id); // Click en cualquier parte del card carga detalles
                jobsListArea.appendChild(li);
            });
        } catch (error) {
            logToTerminal(`Error al cargar historial de trabajos: ${error.message || error}`, "error");
            if (jobsListArea) jobsListArea.innerHTML = '<li class="error-message">Error al cargar trabajos. Intente recargar.</li>';
        }
    }

    function viewJobDetails(jobId) {
        if (!jobId) return;
        logToTerminal(`Cargando detalles para el trabajo ${jobId}...`, "info");
        currentJobId = jobId; // Establecer como job activo en la UI
        localStorage.setItem('currentJobId', jobId); // Guardar en localStorage
        clearTimeout(statusPollInterval); // Detener polling anterior

        if (scanOutput) scanOutput.innerHTML = ''; // Limpiar logs al ver un nuevo job
        displayedLogCount = 0;
        currentJobIdForLogs = jobId; // Establecer para el manejo de logs

        refreshStatus(jobId, true); // true para initialCall, esto actualizará la UI del job y cargará logs iniciales

        document.querySelectorAll('.job-card.active-job-card').forEach(card => card.classList.remove('active-job-card'));
        if (jobsListArea) {
            const activeCard = Array.from(jobsListArea.querySelectorAll('.job-card')).find(card => card.querySelector('.view-details-btn')?.dataset.jobId === jobId);
            if (activeCard) activeCard.classList.add('active-job-card');
        }

        const terminalPanel = document.getElementById('terminal-panel'); // Asumiendo que el panel de output tiene este ID
        if (terminalPanel) {
            terminalPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else { // Fallback si no existe, intentar cambiar a la pestaña de Output
            const outputTabButton = document.querySelector('.tab-link[onclick*="OutputTab"]'); // Asumiendo que el botón de la pestaña tiene este onclick
            if (outputTabButton) outputTabButton.click();
        }
    }

    if (importTargetsButton && importTargetsFile && targetsTextarea) {
        importTargetsButton.onclick = () => importTargetsFile.click();
        importTargetsFile.onchange = (event) => {
            const file = event.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    targetsTextarea.value = e.target.result;
                    logToTerminal(`Targets importados desde ${file.name}`, 'success');
                    updateTargetsCount();
                };
                reader.readAsText(file);
                importTargetsFile.value = ''; // Resetear input para permitir re-seleccionar el mismo archivo
            }
        };
    }

    if (copyLogButton && scanOutput) {
        copyLogButton.onclick = () => {
            if (navigator.clipboard) {
                let logText = "";
                scanOutput.querySelectorAll('.log-entry').forEach(entry => {
                    const timestamp = entry.querySelector('.log-timestamp')?.textContent || "";
                    const message = entry.querySelector('.log-message-content')?.textContent || ""; // Solo texto
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
            let logData = "";
            scanOutput.querySelectorAll('.log-entry').forEach(entry => {
                const timestamp = entry.querySelector('.log-timestamp')?.textContent || "";
                const message = entry.querySelector('.log-message-content')?.textContent || ""; // Solo texto
                logData += `${timestamp} ${message}\n`;
            });
            const blob = new Blob([logData.trim()], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const timestampFile = new Date().toISOString().replace(/[:.]/g, '-');
            a.download = `panthera_scan_log_${currentJobIdForLogs || 'session'}_${timestampFile}.txt`;
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
            tabcontent[i].style.display = "none";
            tabcontent[i].classList.remove("active");
        }
        tablinks = document.getElementsByClassName("tab-link");
        for (i = 0; i < tablinks.length; i++) {
            tablinks[i].classList.remove("active");
        }
        const activeTabContent = document.getElementById(tabName);
        if (activeTabContent) {
            activeTabContent.style.display = "block";
            activeTabContent.classList.add("active");
        }
        if (evt && evt.currentTarget) { // evt puede ser null si se llama programáticamente
            evt.currentTarget.classList.add("active");
        }
    }

    if (scanButton) scanButton.onclick = startScan;
    if (refreshButton) refreshButton.onclick = () => {
        if (currentJobId) refreshStatus(currentJobId, true); // Forzar recarga completa del job actual
        else logToTerminal("No hay un trabajo activo para refrescar.", "info");
    };
    if (cancelJobButton) cancelJobButton.onclick = cancelScan;

    const defaultTabButton = document.querySelector('.tabs .tab-link[data-default-tab="true"]') || document.querySelector('.tabs .tab-link'); // Primer tab como fallback
    if (defaultTabButton) {
        const mockEvent = { currentTarget: defaultTabButton }; // Simular evento para la función openTab
        const tabNameMatch = defaultTabButton.getAttribute('onclick')?.match(/openTab\(event, ['"](.*?)['"]\)/);
        if (tabNameMatch && tabNameMatch[1]) {
            openTab(mockEvent, tabNameMatch[1]);
        }
    }

    fetchAppConfig().then(() => { // Cargar config primero
        if (jobsListArea) loadJobs(); // Luego cargar historial de jobs
        updateTargetsCount(); // Actualizar contador de objetivos inicial
        if (currentJobId) { // Si hay un job guardado en localStorage, intentar cargarlo
            viewJobDetails(currentJobId);
        } else { // Si no hay job activo, asegurar que el panel de info esté oculto
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
            if (cancelJobButton) cancelJobButton.style.display = 'none';
            if (downloadJobZipLink) downloadJobZipLink.style.display = 'none';
        }
    });
});