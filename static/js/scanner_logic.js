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
        window.SCRIPT_ROOT = "";
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
        let iconClass = 'fas fa-info-circle'; // Default FontAwesome
        if (type === 'error') iconClass = 'fas fa-times-circle';
        else if (type === 'warn') iconClass = 'fas fa-exclamation-triangle';
        else if (type === 'success') iconClass = 'fas fa-check-circle';
        else if (type === 'command') iconClass = 'fas fa-terminal'; // o 'fas fa-dollar-sign'
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
            button.innerHTML = `<i class="${profile.icon_class || 'fas fa-id-badge'}"></i> <span>${profileName}</span>`;
            button.title = profile.description || profileName;
            button.dataset.profileName = profileName;
            button.onclick = () => applyScanProfile(profileName);
            profilesContainer.appendChild(button);
        });
        const deselectAllButton = document.createElement('button');
        deselectAllButton.className = 'button-profile-deselect';
        deselectAllButton.innerHTML = '<i class="far fa-square"></i> <span>Desmarcar Todas</span>'; // Usar far para un cuadrado vacío
        deselectAllButton.onclick = () => deselectAllTools();
        profilesContainer.appendChild(deselectAllButton);
    }

    function updateParamsModifiedIndicator(toolId) {
        const toolConfig = appConfig.tools[toolId];
        if (!toolConfig) return;

        const paramsToggleButton = document.getElementById(`params-toggle-${toolId}`);
        if (!paramsToggleButton) return;

        let modified = false;
        const toolCheckboxInput = document.querySelector(`input.tool-item-checkbox[value="${toolId}"]`);
        if (!toolCheckboxInput || !toolCheckboxInput.checked) {
            paramsToggleButton.classList.remove('params-modified');
            const restoreButton = document.getElementById(`restore-${toolId}`);
            if (restoreButton) restoreButton.disabled = true;
            return;
        }

        if (toolConfig.cli_params_config) {
            for (const paramConf of toolConfig.cli_params_config) {
                const inputField = document.getElementById(`cli-${toolId}-${paramConf.name}`);
                if (inputField) {
                    let currentValue;
                    if (paramConf.type === 'checkbox') {
                        currentValue = inputField.checked;
                    } else {
                        currentValue = inputField.value;
                    }
                    const defaultValue = paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.type === 'checkbox' ? false : '');
                    if (currentValue !== defaultValue) {
                        modified = true;
                        break;
                    }
                }
            }
        }

        if (!modified && toolConfig.allow_additional_args) {
            const additionalArgsInput = document.getElementById(`cli-additional-${toolId}`);
            if (additionalArgsInput && additionalArgsInput.value.trim() !== '') {
                modified = true;
            }
        }

        paramsToggleButton.classList.toggle('params-modified', modified);

        const restoreButton = document.getElementById(`restore-${toolId}`);
        if (restoreButton) {
            restoreButton.disabled = !modified;
        }
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
            const phaseKey = tool.phase;
            const categoryKey = tool.category;
            if (!toolsByPhaseAndCategory[phaseKey]) {
                toolsByPhaseAndCategory[phaseKey] = {
                    meta: appConfig.phases[phaseKey] || { name: phaseKey, order: 99, icon_class: 'fas fa-question-circle' },
                    categories: {}
                };
            }
            if (!toolsByPhaseAndCategory[phaseKey].categories[categoryKey]) {
                toolsByPhaseAndCategory[phaseKey].categories[categoryKey] = {
                    display_name: tool.category_display_name || categoryKey,
                    icon_class: tool.category_icon_class || 'fas fa-folder',
                    tools: []
                };
            }
            if (tool.cli_params_config) {
                tool.cli_params_config.forEach(p => p.original_default = p.default);
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
            const phaseIconClass = phaseData.meta.icon_class || 'fas fa-layer-group';
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
                const categoryIconClass = categoryData.icon_class || 'fas fa-folder';
                const categoryHeader = document.createElement('div');
                categoryHeader.className = 'tool-category-header';
                categoryHeader.innerHTML = `
                    <label class="toggle-switch">
                        <input type="checkbox" id="${categoryId}" class="tool-category-checkbox" data-phase-parent-id="${phaseId}" data-type="category">
                        <span class="slider"></span>
                    </label>
                    <h5><i class="${categoryIconClass}"></i> ${categoryDisplayName}</h5>
                    <span class="accordion-arrow"><i class="fas fa-chevron-down"></i></span>`;
                const toolItemsContainer = document.createElement('div');
                toolItemsContainer.className = 'tool-items-container';
                categoryHeader.onclick = (e) => {
                    if (e.target.type === 'checkbox' || e.target.classList.contains('slider') || e.target.closest('.toggle-switch')) return;
                    toolItemsContainer.classList.toggle('expanded');
                    categoryHeader.classList.toggle('expanded'); // Para la flecha
                    const arrowIcon = categoryHeader.querySelector('.accordion-arrow i');
                    if (arrowIcon) {
                        arrowIcon.className = toolItemsContainer.classList.contains('expanded') ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
                    }
                };
                categoryDiv.appendChild(categoryHeader);

                categoryData.tools.forEach(tool => {
                    const toolItemId = `tool-toggle-${tool.id}-${uniqueIdCounter++}`;
                    const toolItemDiv = document.createElement('div');
                    toolItemDiv.className = 'tool-item';
                    let paramsToggleButtonHtml = '';
                    const hasPredefinedParams = tool.cli_params_config && tool.cli_params_config.length > 0;
                    const allowsAdditionalArgs = tool.allow_additional_args;

                    if (hasPredefinedParams || allowsAdditionalArgs) {
                        paramsToggleButtonHtml = `
                            <button class="tool-params-toggle-btn" id="params-toggle-${tool.id}" title="Configurar parámetros de ${tool.name}">
                                <i class="fas fa-sliders-h"></i>
                            </button>`;
                    }

                    let toolDetailsContentHtml = '';
                    if (hasPredefinedParams || allowsAdditionalArgs) {
                        toolDetailsContentHtml += `<div class="tool-details-header">
                                                     <h6><i class="fas fa-cogs"></i> Configuración de ${tool.name}</h6>
                                                     <button class="restore-defaults-btn" id="restore-${tool.id}" title="Restaurar parámetros a sus valores por defecto" disabled>
                                                         <i class="fas fa-undo"></i> Restaurar
                                                     </button>
                                                   </div>`;
                    }

                    if (hasPredefinedParams) {
                        toolDetailsContentHtml += `<div class="tool-cli-params-group">`;
                        tool.cli_params_config.forEach(paramConf => {
                            toolDetailsContentHtml += `<div class="cli-param-row ${paramConf.type === 'checkbox' ? 'cli-param-checkbox' : ''}">`;
                            if (paramConf.type === 'checkbox') {
                                toolDetailsContentHtml += `
                                    <input type="checkbox" id="cli-${tool.id}-${paramConf.name}" 
                                           name="cli_param_${tool.id}_${paramConf.name}" 
                                           ${(paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || false)) ? 'checked' : ''} 
                                           title="${paramConf.description || ''}"
                                           data-tool-id="${tool.id}" data-param-name="${paramConf.name}">
                                    <label for="cli-${tool.id}-${paramConf.name}" title="${paramConf.description || ''}">${paramConf.label}</label>`;
                            } else {
                                toolDetailsContentHtml += `<label for="cli-${tool.id}-${paramConf.name}" title="${paramConf.description || ''}">${paramConf.label}:</label>`;
                                if (paramConf.type === 'select') {
                                    toolDetailsContentHtml += `<select id="cli-${tool.id}-${paramConf.name}" name="cli_param_${tool.id}_${paramConf.name}" title="${paramConf.description || ''}" data-tool-id="${tool.id}" data-param-name="${paramConf.name}">`;
                                    (paramConf.options || []).forEach(opt => {
                                        const value = typeof opt === 'string' ? opt : opt.value;
                                        const label = typeof opt === 'string' ? opt : opt.label;
                                        toolDetailsContentHtml += `<option value="${value}" ${value === (paramConf.original_default !== undefined ? paramConf.original_default : paramConf.default) ? 'selected' : ''}>${label}</option>`;
                                    });
                                    toolDetailsContentHtml += `</select>`;
                                } else if (paramConf.type === 'textarea') {
                                    toolDetailsContentHtml += `<textarea id="cli-${tool.id}-${paramConf.name}" 
                                                                      name="cli_param_${tool.id}_${paramConf.name}" 
                                                                      placeholder="${paramConf.placeholder || ''}" 
                                                                      title="${paramConf.description || ''}"
                                                                      data-tool-id="${tool.id}" data-param-name="${paramConf.name}">${paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || '')}</textarea>`;
                                } else {
                                    toolDetailsContentHtml += `<input type="${paramConf.type || 'text'}" 
                                                                      id="cli-${tool.id}-${paramConf.name}" 
                                                                      name="cli_param_${tool.id}_${paramConf.name}" 
                                                                      placeholder="${paramConf.placeholder || ''}" 
                                                                      value="${paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || '')}" 
                                                                      title="${paramConf.description || ''}"
                                                                      data-tool-id="${tool.id}" data-param-name="${paramConf.name}">`;
                                }
                            }
                            toolDetailsContentHtml += `</div>`;
                        });
                        toolDetailsContentHtml += `</div>`;
                    }

                    if (allowsAdditionalArgs) {
                        toolDetailsContentHtml += `<div class="cli-param-row additional-args-row">
                                                    <label for="cli-additional-${tool.id}" title="Argumentos CLI adicionales, separados por espacio. No incluyas el objetivo aquí.">Argumentos Adicionales:</label>
                                                    <input type="text" id="cli-additional-${tool.id}" 
                                                           name="cli_additional_args_${tool.id}" 
                                                           class="additional-args-input" 
                                                           placeholder="${tool.additional_args_placeholder || 'ej: --opcion valor -flag'}"
                                                           data-tool-id="${tool.id}">
                                                  </div>`;
                    }

                    const toolIconClass = tool.icon_class || 'fas fa-cog';
                    const dangerousIndicator = tool.dangerous ? `<span class="tool-dangerous-indicator" title="Esta herramienta puede ser intrusiva o disruptiva"><i class="fas fa-exclamation-triangle"></i></span>` : '';

                    toolItemDiv.innerHTML = `
                        <div class="tool-item-main">
                            <label class="toggle-switch">
                                <input type="checkbox" id="${toolItemId}" name="selected_tools" value="${tool.id}" class="tool-item-checkbox" data-category-parent-id="${categoryId}" data-type="tool" ${tool.default_enabled ? 'checked' : ''}>
                                <span class="slider"></span>
                            </label>
                            <span class="tool-icon"><i class="${toolIconClass}"></i></span>
                            <span class="toggle-label" title="${tool.description || tool.name}">${tool.name}</span>
                            ${dangerousIndicator}
                            ${paramsToggleButtonHtml} 
                        </div>
                        <div class="tool-details" id="details-${tool.id}">${toolDetailsContentHtml}</div>`;
                    toolItemsContainer.appendChild(toolItemDiv);

                    const paramsToggleButton = toolItemDiv.querySelector(`#params-toggle-${tool.id}`);
                    const toolDetailsDiv = toolItemDiv.querySelector(`#details-${tool.id}`);
                    const toolCheckboxInput = toolItemDiv.querySelector('.tool-item-checkbox');

                    if (paramsToggleButton && toolDetailsDiv) {
                        paramsToggleButton.addEventListener('click', () => {
                            toolDetailsDiv.classList.toggle('expanded');
                            paramsToggleButton.classList.toggle('active', toolDetailsDiv.classList.contains('expanded'));
                        });
                    }

                    if (toolCheckboxInput && toolDetailsDiv && (hasPredefinedParams || allowsAdditionalArgs)) {
                        toolCheckboxInput.addEventListener('change', (e) => {
                            const isChecked = e.target.checked;
                            if (!isChecked) {
                                toolDetailsDiv.classList.remove('expanded');
                                if (paramsToggleButton) paramsToggleButton.classList.remove('active');
                            }
                            updateParamsModifiedIndicator(tool.id);
                        });
                    }

                    const restoreButton = toolItemDiv.querySelector(`#restore-${tool.id}`);
                    if (restoreButton) {
                        restoreButton.addEventListener('click', () => {
                            if (tool.cli_params_config) {
                                tool.cli_params_config.forEach(paramConf => {
                                    const inputField = toolItemDiv.querySelector(`#cli-${tool.id}-${paramConf.name}`);
                                    if (inputField) {
                                        if (paramConf.type === 'checkbox') {
                                            inputField.checked = paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || false);
                                        } else {
                                            inputField.value = paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || '');
                                        }
                                    }
                                });
                            }
                            if (tool.allow_additional_args) {
                                const additionalArgsInput = toolItemDiv.querySelector(`#cli-additional-${tool.id}`);
                                if (additionalArgsInput) {
                                    additionalArgsInput.value = '';
                                }
                            }
                            updateParamsModifiedIndicator(tool.id);
                            logToTerminal(`Parámetros de '${tool.name}' restaurados a los valores por defecto.`, 'info');
                        });
                    }

                    toolItemDiv.querySelectorAll(`[data-tool-id="${tool.id}"]`).forEach(input => {
                        input.addEventListener('input', () => updateParamsModifiedIndicator(tool.id));
                        input.addEventListener('change', () => updateParamsModifiedIndicator(tool.id));
                    });
                    if (toolCheckboxInput.checked) {
                        updateParamsModifiedIndicator(tool.id);
                    } else {
                        if (restoreButton) restoreButton.disabled = true;
                    }
                });
                categoryDiv.appendChild(toolItemsContainer);
                phaseDiv.appendChild(categoryDiv);
            }
            toolListDiv.appendChild(phaseDiv);
        }

        addCheckboxEventListeners();
        updateAllParentCheckboxes();
        document.querySelectorAll('.tool-items-container').forEach(container => {
            container.classList.remove('expanded');
            const header = container.previousElementSibling;
            if (header && header.classList.contains('tool-category-header')) {
                header.classList.remove('expanded');
                const arrowIcon = header.querySelector('.accordion-arrow i');
                if (arrowIcon) arrowIcon.className = 'fas fa-chevron-down';
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
                    toggleChildren(catCb, checkbox.checked);
                });
            }
        } else if (type === 'category') {
            toggleChildren(checkbox, checkbox.checked);
            updateParentCheckboxState(checkbox.dataset.phaseParentId);
        } else if (type === 'tool') {
            updateParentCheckboxState(checkbox.dataset.categoryParentId);
        }
    }

    function toggleChildren(parentCheckbox, isChecked) {
        const parentType = parentCheckbox.dataset.type;
        let childrenSelector = '';
        if (parentType === 'category') {
            childrenSelector = `.tool-item-checkbox[data-category-parent-id="${parentCheckbox.id}"]`;
        }

        if (childrenSelector) {
            const categoryDiv = parentCheckbox.closest('.tool-category');
            if (!categoryDiv) return;

            categoryDiv.querySelectorAll(childrenSelector).forEach(childCb => {
                childCb.checked = isChecked;
                childCb.indeterminate = false;
                const toolItem = childCb.closest('.tool-item');
                if (toolItem) {
                    const toolDetailsDiv = toolItem.querySelector('.tool-details');
                    const paramsToggleBtn = toolItem.querySelector(`.tool-params-toggle-btn[id="params-toggle-${childCb.value}"]`);
                    if (toolDetailsDiv) {
                        if (!isChecked) {
                            toolDetailsDiv.classList.remove('expanded');
                            if (paramsToggleBtn) paramsToggleBtn.classList.remove('active');
                        }
                    }
                    updateParamsModifiedIndicator(childCb.value);
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
            return;
        }
        const childrenArray = Array.from(childrenCheckboxesNodeList);
        if (childrenArray.length === 0) {
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
            updateParamsModifiedIndicator(toolCb.value);
        });
        toolListDiv.querySelectorAll('.tool-category-checkbox').forEach(catCb => {
            updateParentCheckboxState(catCb.id);
        });
        toolListDiv.querySelectorAll('.pentest-phase-header input[type="checkbox"]').forEach(phaseCb => {
            updateParentCheckboxState(phaseCb.id);
        });
    }

    window.applyScanProfile = function (profileName) {
        deselectAllTools();
        const profile = appConfig.profiles[profileName];
        if (profile && profile.tools && toolListDiv) {
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
                        if (paramName === 'additional_args') {
                            const additionalArgsInput = document.getElementById(`cli-additional-${toolId}`);
                            if (additionalArgsInput) {
                                additionalArgsInput.value = toolParams.additional_args;
                                additionalArgsInput.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        } else {
                            const inputField = document.getElementById(`cli-${toolId}-${paramName}`);
                            if (inputField) {
                                if (inputField.type === 'checkbox') {
                                    inputField.checked = toolParams[paramName];
                                } else {
                                    inputField.value = toolParams[paramName];
                                }
                                inputField.dispatchEvent(new Event('input', { bubbles: true }));
                                inputField.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        }
                    }
                }
            }
            logToTerminal(`Perfil '${profileName}' aplicado.`, 'success');
        }
        updateAllParentCheckboxes();
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
                if (checkbox.dataset.type === 'tool') {
                    const toolItem = checkbox.closest('.tool-item');
                    if (toolItem) {
                        const toolDetailsDiv = toolItem.querySelector('.tool-details');
                        const paramsToggleBtn = toolItem.querySelector(`.tool-params-toggle-btn`);
                        if (toolDetailsDiv) toolDetailsDiv.classList.remove('expanded');
                        if (paramsToggleBtn) {
                            paramsToggleBtn.classList.remove('active');
                        }
                        const toolId = checkbox.value;
                        const tool = appConfig.tools[toolId];
                        if (tool && tool.cli_params_config) {
                            tool.cli_params_config.forEach(paramConf => {
                                const inputField = document.getElementById(`cli-${toolId}-${paramConf.name}`);
                                if (inputField) {
                                    if (paramConf.type === 'checkbox') inputField.checked = paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || false);
                                    else inputField.value = paramConf.original_default !== undefined ? paramConf.original_default : (paramConf.default || '');
                                }
                            });
                        }
                        if (tool && tool.allow_additional_args) {
                            const additionalArgsInput = document.getElementById(`cli-additional-${toolId}`);
                            if (additionalArgsInput) additionalArgsInput.value = '';
                        }
                        updateParamsModifiedIndicator(toolId);
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
            const toolConfig = appConfig.tools[toolId];
            let params = {};

            if (toolConfig && toolConfig.cli_params_config) {
                toolConfig.cli_params_config.forEach(pConf => {
                    const inputField = document.getElementById(`cli-${toolId}-${pConf.name}`);
                    if (inputField) {
                        if (pConf.type === 'checkbox') {
                            params[pConf.name] = inputField.checked;
                        } else {
                            params[pConf.name] = inputField.value;
                        }
                    } else {
                        params[pConf.name] = pConf.original_default !== undefined ? pConf.original_default : pConf.default;
                    }
                });
            }

            let additionalArgs = '';
            if (toolConfig && toolConfig.allow_additional_args) {
                const additionalArgsInput = document.getElementById(`cli-additional-${toolId}`);
                if (additionalArgsInput && additionalArgsInput.value.trim() !== '') {
                    additionalArgs = additionalArgsInput.value.trim();
                }
            }

            selectedToolsPayload.push({
                id: toolId,
                cli_params: params,
                additional_args: additionalArgs
            });
        });

        if (selectedToolsPayload.length === 0) {
            logToTerminal("Por favor, seleccione al menos una herramienta de escaneo.", "error");
            return;
        }
        const advancedScanOptions = {
            customScanTime: document.getElementById('customScanTime')?.value || null,
            followRedirects: document.getElementById('followRedirects')?.checked || false,
            scanIntensity: document.getElementById('scanIntensity')?.value || 'normal',
            tool_timeout: document.getElementById('toolTimeout')?.value || null,
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
        if (cancelJobButton) cancelJobButton.style.display = 'inline-block';
        if (downloadJobZipLink) {
            downloadJobZipLink.style.display = 'none';
            downloadJobZipLink.classList.add('disabled');
            downloadJobZipLink.href = '#';
        }
        if (scanButton) {
            scanButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Escaneando...';
            scanButton.disabled = true;
        }
        if (scanOutput) scanOutput.innerHTML = '';
        const toolProgressDetailsDiv = document.getElementById('toolProgressDetails');
        if (toolProgressDetailsDiv) {
            toolProgressDetailsDiv.innerHTML = '<p class="empty-placeholder">Esperando inicio de escaneo...</p>';
        }
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
                refreshStatus(currentJobId, true);
                if (jobsListArea) loadJobs();
            } else {
                logToTerminal(`Error al iniciar escaneo (HTTP ${response.status}): ${data.error || 'Error desconocido del servidor'}`, "error");
                if (jobInfoPanel) jobInfoPanel.style.display = 'none';
                if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
                if (scanButton) {
                    scanButton.innerHTML = '<i class="fas fa-bolt"></i> Iniciar Escaneo';
                    scanButton.disabled = false;
                }
            }
        } catch (error) {
            logToTerminal(`Error de red al iniciar escaneo: ${error.message || error}`, "error");
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
            if (scanButton) {
                scanButton.innerHTML = '<i class="fas fa-bolt"></i> Iniciar Escaneo';
                scanButton.disabled = false;
            }
        }
    }

    async function refreshStatus(jobIdToRefresh = null, initialCall = false) {
        const effectiveJobId = jobIdToRefresh || currentJobId;
        if (!effectiveJobId) {
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
            if (cancelJobButton) cancelJobButton.style.display = 'none';
            if (downloadJobZipLink) {
                downloadJobZipLink.style.display = 'none';
                downloadJobZipLink.classList.add('disabled');
            }
            return;
        }

        if (initialCall) {
            if (jobIdDisplay) jobIdDisplay.textContent = effectiveJobId;
            if (jobInfoPanel) jobInfoPanel.style.display = 'block';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'block';
        }

        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/scan/status/${effectiveJobId}`);
            if (!response.ok) {
                if (response.status === 404) {
                    logToTerminal(`Job ID ${effectiveJobId} no encontrado. Pudo haber sido purgado o es inválido.`, "warn");
                    if (effectiveJobId === currentJobId) {
                        localStorage.removeItem('currentJobId');
                        currentJobId = null; currentJobIdForLogs = null; displayedLogCount = 0;
                        if (jobInfoPanel) jobInfoPanel.style.display = 'none';
                        if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
                        clearTimeout(statusPollInterval);
                        if (scanButton) { scanButton.innerHTML = '<i class="fas fa-bolt"></i> Iniciar Escaneo'; scanButton.disabled = false; }
                        if (jobStatusBadge) { jobStatusBadge.textContent = 'N/A'; jobStatusBadge.className = 'status-badge status-unknown'; }
                        if (overallProgressBar) { overallProgressBar.style.width = `0%`; overallProgressBar.setAttribute('aria-valuenow', 0); overallProgressBar.textContent = `0%`; }
                        const toolProgressDetailsDiv = document.getElementById('toolProgressDetails');
                        if (toolProgressDetailsDiv) toolProgressDetailsDiv.innerHTML = '<p class="empty-placeholder">Seleccione un trabajo del historial o inicie uno nuevo.</p>';
                    }
                } else {
                    const errorData = await response.json().catch(() => ({ error: "Error desconocido al obtener estado." }));
                    logToTerminal(`Error al obtener estado del Job ${effectiveJobId} (HTTP ${response.status}): ${errorData.error || 'Error de servidor'}`, "error");
                }
                return;
            }

            const data = await response.json();
            if (!data || !data.job_id) {
                logToTerminal(`Respuesta inválida del servidor para el estado del Job ${effectiveJobId}.`, "error");
                return;
            }

            if (jobIdDisplay) jobIdDisplay.textContent = data.job_id;
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


            if (currentJobIdForLogs !== data.job_id || initialCall) {
                if (scanOutput) scanOutput.innerHTML = '';
                displayedLogCount = 0;
                if (currentJobIdForLogs !== data.job_id || (initialCall && (!scanOutput || scanOutput.innerHTML === ''))) {
                    logToTerminal(`Mostrando logs para Job ID: ${data.job_id}`, 'info');
                }
                currentJobIdForLogs = data.job_id;
            }

            if (data.logs && Array.isArray(data.logs)) {
                const newLogs = data.logs.slice(displayedLogCount);
                newLogs.forEach(log => {
                    let logDisplayType = (log.level || 'info').toLowerCase();
                    const validDisplayTypes = ['info', 'error', 'warn', 'success', 'command'];
                    if (!validDisplayTypes.includes(logDisplayType)) {
                        logDisplayType = (logDisplayType === 'debug') ? 'info' : 'info';
                    }
                    logToTerminal(log.message, logDisplayType, log.is_html || false);
                });
                displayedLogCount = data.logs.length;
            }

            const toolProgressDetailsDiv = document.getElementById('toolProgressDetails');
            if (toolProgressDetailsDiv) {
                if (data.tool_progress && Object.keys(data.tool_progress).length > 0) {
                    toolProgressDetailsDiv.innerHTML = '';
                    const sortedToolKeys = Object.keys(data.tool_progress).sort((a, b) => {
                        const statusA = data.tool_progress[a].status.toLowerCase();
                        const statusB = data.tool_progress[b].status.toLowerCase();
                        const order = { running: 0, pending: 1 };
                        const orderValA = order[statusA] !== undefined ? order[statusA] : 2;
                        const orderValB = order[statusB] !== undefined ? order[statusB] : 2;
                        if (orderValA !== orderValB) return orderValA - orderValB;
                        return (data.tool_progress[a].name || "").localeCompare(data.tool_progress[b].name || "");
                    });

                    sortedToolKeys.forEach(toolKey => {
                        const toolProg = data.tool_progress[toolKey];
                        const itemDiv = document.createElement('div');
                        itemDiv.className = 'tool-progress-item';
                        let statusIcon = 'fas fa-hourglass-half';
                        let statusText = toolProg.status ? toolProg.status.charAt(0).toUpperCase() + toolProg.status.slice(1) : 'Desconocido';
                        let statusClass = `tool-status-${toolProg.status ? toolProg.status.toLowerCase().replace(/_/g, '-') : 'unknown'}`;

                        if (toolProg.status) {
                            const lowerStatus = toolProg.status.toLowerCase();
                            if (lowerStatus === 'running') statusIcon = 'fas fa-spinner fa-spin';
                            else if (lowerStatus === 'completed') statusIcon = 'fas fa-check-circle';
                            else if (lowerStatus === 'error' || lowerStatus === 'timeout') statusIcon = 'fas fa-times-circle';
                            else if (lowerStatus === 'skipped') statusIcon = 'fas fa-forward';
                            else if (lowerStatus === 'cancelled') statusIcon = 'fas fa-ban';
                        }

                        const toolDefinitionFromConfig = appConfig.tools[toolProg.id]; // Usar toolProg.id (que debe ser el tool_id)
                        const iconClass = toolDefinitionFromConfig ? toolDefinitionFromConfig.icon_class : 'fas fa-cog';

                        itemDiv.innerHTML = `
                            <span class="tool-progress-name"><i class="${iconClass}"></i> ${toolProg.name || 'Herramienta Desconocida'}</span>
                            <span class="tool-progress-status ${statusClass}">
                                <i class="${statusIcon}"></i> ${statusText}
                            </span>
                        `;
                        let titleText = `Comando: ${toolProg.command || 'N/A'}`;
                        if (toolProg.error_message) titleText += `\nError: ${toolProg.error_message}`;
                        if (toolProg.output_file) titleText += `\nSalida: ${toolProg.output_file}`;
                        itemDiv.title = titleText;
                        toolProgressDetailsDiv.appendChild(itemDiv);
                    });
                } else if (initialCall || !toolProgressDetailsDiv.innerHTML.includes('tool-progress-item')) {
                    toolProgressDetailsDiv.innerHTML = '<p class="empty-placeholder">No hay detalles de herramientas para este trabajo aún.</p>';
                }
            }

            const terminalStates = ['COMPLETED', 'CANCELLED', 'ERROR', 'COMPLETED_WITH_ERRORS'];
            if (terminalStates.includes(data.status?.toUpperCase())) {
                if (cancelJobButton) cancelJobButton.style.display = 'none';
                if (data.zip_path && downloadJobZipLink) {
                    downloadJobZipLink.href = `${SCRIPT_ROOT}${data.zip_path}`;
                    downloadJobZipLink.style.display = 'inline-block';
                    downloadJobZipLink.classList.remove('disabled');
                } else if (downloadJobZipLink) {
                    downloadJobZipLink.style.display = 'none';
                    downloadJobZipLink.classList.add('disabled');
                }
                if (effectiveJobId === currentJobId) {
                    if (scanButton) { scanButton.innerHTML = '<i class="fas fa-bolt"></i> Iniciar Escaneo'; scanButton.disabled = false; }
                }
                clearTimeout(statusPollInterval);
                if (jobsListArea) loadJobs();
            } else {
                if (cancelJobButton) cancelJobButton.style.display = 'inline-block';
                if (downloadJobZipLink) {
                    downloadJobZipLink.style.display = 'none';
                    downloadJobZipLink.classList.add('disabled');
                }
                clearTimeout(statusPollInterval);
                statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 3000);
            }

        } catch (error) {
            logToTerminal(`Error de red al obtener estado del Job ${effectiveJobId}: ${error.message || error}`, "error");
            clearTimeout(statusPollInterval);
            statusPollInterval = setTimeout(() => refreshStatus(effectiveJobId), 7000);
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
            const data = await response.json();
            if (response.ok) {
                logToTerminal(`Solicitud de cancelación enviada para el trabajo ${jobIdToCancel}. Estado: ${data.message || 'OK'}.`, "info");
                if (jobStatusBadge) {
                    jobStatusBadge.textContent = "Cancelando...";
                    jobStatusBadge.className = 'status-badge status-cancelling';
                }
                if (cancelJobButton) cancelJobButton.style.display = 'none';
                clearTimeout(statusPollInterval);
                statusPollInterval = setTimeout(() => refreshStatus(jobIdToCancel), 1500);
            } else {
                logToTerminal(`Error al cancelar escaneo (HTTP ${response.status}): ${data.error || data.message || 'Error desconocido'}`, "error");
            }
        } catch (error) {
            logToTerminal(`Error de red al cancelar escaneo: ${error.message || error}`, "error");
        }
    }

    async function loadJobs() {
        if (!jobsListArea) return;
        jobsListArea.innerHTML = '<li class="loading-placeholder"><i class="fas fa-spinner fa-spin"></i> Cargando historial...</li>';
        try {
            const response = await fetch(`${SCRIPT_ROOT}/api/jobs`);
            if (!response.ok) throw new Error(`HTTP error ${response.status}`);
            const jobs = await response.json();
            jobsListArea.innerHTML = '';
            if (!jobs || jobs.length === 0) {
                jobsListArea.innerHTML = '<li class="empty-placeholder">No hay trabajos anteriores.</li>';
                return;
            }
            jobs.forEach(job => {
                const li = document.createElement('li');
                const statusClass = (job.status || 'unknown').toLowerCase().replace(/_/g, '-');
                li.classList.add('job-card', `status-${statusClass}`);
                if (job.id === currentJobId) {
                    li.classList.add('active-job-card');
                }
                let targetsDisplay = Array.isArray(job.targets) ? job.targets.join(', ') : (job.targets || 'N/A');
                if (targetsDisplay.length > 35) targetsDisplay = targetsDisplay.substring(0, 32) + '...';

                let statusIconClass = 'fas fa-question-circle';
                const upperStatus = (job.status || '').toUpperCase();
                if (upperStatus === 'COMPLETED') statusIconClass = 'fas fa-check-circle icon-check-circle-green';
                else if (upperStatus === 'COMPLETED_WITH_ERRORS') statusIconClass = 'fas fa-exclamation-circle icon-check-circle-orange';
                else if (upperStatus === 'RUNNING') statusIconClass = 'fas fa-spinner fa-spin icon-spinner blue';
                else if (upperStatus === 'ERROR') statusIconClass = 'fas fa-times-circle icon-times-circle-red';
                else if (upperStatus === 'CANCELLED') statusIconClass = 'fas fa-ban icon-ban grey';
                else if (upperStatus === 'PENDING' || upperStatus === 'INITIALIZING' || upperStatus === 'REQUEST_CANCEL' || upperStatus === 'CANCELLING') statusIconClass = 'fas fa-clock icon-clock orange';

                li.innerHTML = `
                    <div class="job-card-header">
                        <span class="job-id">ID: ${job.id}</span>
                        <span class="job-status job-status-${statusClass}">
                            <i class="${statusIconClass}"></i> ${job.status || 'Desconocido'}
                        </span>
                    </div>
                    <div class="job-card-body">
                        <p class="job-targets" title="${Array.isArray(job.targets) ? job.targets.join(', ') : (job.targets || 'N/A')}">
                            <strong><i class="fas fa-bullseye"></i> Objetivos:</strong> ${targetsDisplay}
                        </p>
                        <p class="job-timestamp">
                            <strong><i class="fas fa-calendar-alt"></i> Fecha:</strong> ${job.timestamp ? new Date(job.timestamp).toLocaleString() : 'N/A'}
                        </p>
                    </div>
                    <div class="job-card-actions">
                        <button class="button-secondary view-details-btn" data-job-id="${job.id}">
                            <i class="fas fa-eye"></i> Ver Detalles
                        </button>
                        ${job.zip_path ? `<a href="${SCRIPT_ROOT}${job.zip_path}" class="button-success download-zip-btn" target="_blank" rel="noopener noreferrer">
                                            <i class="fas fa-download"></i> Descargar ZIP
                                         </a>` :
                        `<button class="button-disabled download-zip-btn" disabled title="Resultados no disponibles para descarga">
                                            <i class="fas fa-download"></i> Descargar ZIP
                                        </button>`}
                    </div>`;
                const viewDetailsBtn = li.querySelector('.view-details-btn');
                if (viewDetailsBtn) {
                    viewDetailsBtn.onclick = (e) => {
                        e.stopPropagation();
                        viewJobDetails(job.id);
                    };
                }
                li.onclick = () => viewJobDetails(job.id);
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
        currentJobId = jobId;
        localStorage.setItem('currentJobId', jobId);
        clearTimeout(statusPollInterval);

        if (scanOutput) scanOutput.innerHTML = '';
        displayedLogCount = 0;
        currentJobIdForLogs = jobId;

        refreshStatus(jobId, true);

        document.querySelectorAll('.job-card.active-job-card').forEach(card => card.classList.remove('active-job-card'));
        if (jobsListArea) {
            const activeCard = Array.from(jobsListArea.querySelectorAll('.job-card')).find(card => card.querySelector('.view-details-btn')?.dataset.jobId === jobId);
            if (activeCard) activeCard.classList.add('active-job-card');
        }

        const terminalPanel = document.getElementById('terminal-panel');
        if (terminalPanel) {
            terminalPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            const outputTabButton = document.querySelector('.tab-link[onclick*="OutputTab"]');
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
                importTargetsFile.value = '';
            }
        };
    }

    if (copyLogButton && scanOutput) {
        copyLogButton.onclick = () => {
            if (navigator.clipboard) {
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
            let logData = "";
            scanOutput.querySelectorAll('.log-entry').forEach(entry => {
                const timestamp = entry.querySelector('.log-timestamp')?.textContent || "";
                const message = entry.querySelector('.log-message-content')?.textContent || "";
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
        if (evt && evt.currentTarget) {
            evt.currentTarget.classList.add("active");
        }
    }

    if (scanButton) scanButton.onclick = startScan;
    if (refreshButton) refreshButton.onclick = () => {
        if (currentJobId) refreshStatus(currentJobId, true);
        else logToTerminal("No hay un trabajo activo para refrescar.", "info");
    };
    if (cancelJobButton) cancelJobButton.onclick = cancelScan;

    const defaultTabButton = document.querySelector('.tabs .tab-link[data-default-tab="true"]') || document.querySelector('.tabs .tab-link');
    if (defaultTabButton) {
        const mockEvent = { currentTarget: defaultTabButton };
        const tabNameMatch = defaultTabButton.getAttribute('onclick')?.match(/openTab\(event, ['"](.*?)['"]\)/);
        if (tabNameMatch && tabNameMatch[1]) {
            openTab(mockEvent, tabNameMatch[1]);
        }
    }

    fetchAppConfig().then(() => {
        if (jobsListArea) loadJobs();
        updateTargetsCount();
        if (currentJobId) {
            viewJobDetails(currentJobId);
        } else {
            if (jobInfoPanel) jobInfoPanel.style.display = 'none';
            if (currentJobInfoDiv) currentJobInfoDiv.style.display = 'none';
            if (cancelJobButton) cancelJobButton.style.display = 'none';
            if (downloadJobZipLink) downloadJobZipLink.style.display = 'none';
            const toolProgressDetailsDiv = document.getElementById('toolProgressDetails');
            if (toolProgressDetailsDiv) toolProgressDetailsDiv.innerHTML = '<p class="empty-placeholder">Seleccione un trabajo del historial o inicie uno nuevo.</p>';
        }
    });
});