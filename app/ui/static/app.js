/**
 * Case-to-Clearance Single Window Copilot
 * Frontend JavaScript for HTMX-powered interactions
 */

(function() {
    'use strict';

    // ============================================================================
    // CONSTANTS
    // ============================================================================

    const API_BASE = '/api';
    const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20MB
    const ALLOWED_EXTENSIONS = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp'];

    // ============================================================================
    // STATE MANAGEMENT
    // ============================================================================

    const AppState = {
        caseId: null,
        currentStage: 'intake', // intake, documents, risk
        isLoading: false,

        setCaseId(id) {
            this.caseId = id;
            sessionStorage.setItem('caseId', id);
            this.updateURL();
        },

        getCaseId() {
            if (!this.caseId) {
                this.caseId = sessionStorage.getItem('caseId');
            }
            return this.caseId;
        },

        updateURL() {
            if (this.caseId) {
                history.pushState({ caseId: this.caseId }, '', `/ui/case/${this.caseId}`);
            }
        },

        setStage(stage) {
            this.currentStage = stage;
            this.updateStageIndicators();
            this.updateWizardProgress(stage);
        },

        updateStageIndicators() {
            document.querySelectorAll('.stage-indicator').forEach(el => {
                const stage = el.dataset.stage;
                el.classList.remove('active', 'completed');
                if (stage === this.currentStage) {
                    el.classList.add('active');
                }
                // Could add logic for completed stages
            });
        },

        updateWizardProgress(stage) {
            const stages = ['intake', 'documents', 'risk'];
            const currentIndex = stages.indexOf(stage);
            const stepHeadings = {
                intake: 'Describe your customs request',
                documents: 'Upload required documents',
                risk: 'Review risk assessment'
            };

            // Update step counter
            const currentStepEl = document.querySelector('.wizard-current-step');
            if (currentStepEl) {
                currentStepEl.textContent = currentIndex + 1;
            }

            // Update heading text
            const headingText = document.querySelector('.wizard-heading-text');
            if (headingText) {
                headingText.textContent = stepHeadings[stage];
            }

            // Update step indicators
            document.querySelectorAll('.wizard-step').forEach((el, index) => {
                el.classList.remove('completed', 'current');
                el.removeAttribute('aria-current');

                if (index < currentIndex) {
                    el.classList.add('completed');
                } else if (index === currentIndex) {
                    el.classList.add('current');
                    el.setAttribute('aria-current', 'true');
                }
            });

            // Update instructions
            document.querySelectorAll('.instruction-card').forEach(el => {
                el.style.display = 'none';
            });
            const activeInstruction = document.querySelector(`.instruction-card[data-step="${stage}"]`);
            if (activeInstruction) {
                activeInstruction.style.display = 'block';
            }
        }
    };

    // ============================================================================
    // API HELPERS
    // ============================================================================

    const API = {
        async post(endpoint, data, formData = false) {
            const options = {
                method: 'POST',
                headers: {}
            };

            if (formData) {
                const fd = new FormData();
                Object.entries(data).forEach(([key, value]) => {
                    if (Array.isArray(value)) {
                        value.forEach(v => fd.append(key, v));
                    } else {
                        fd.append(key, value);
                    }
                });
                options.body = fd;
            } else {
                options.headers['Content-Type'] = 'application/json';
                options.body = JSON.stringify(data);
            }

            const response = await fetch(endpoint, options);
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error?.message || 'Request failed');
            }
            return response.json();
        },

        async get(endpoint) {
            const response = await fetch(endpoint);
            if (!response.ok) {
                throw new Error('Request failed');
            }
            return response.json();
        }
    };

    // ============================================================================
    // UI COMPONENTS
    // ============================================================================

    const UI = {
        // Global overlay loader
        showLoading(show = true, message = 'Processing...') {
            const loader = document.getElementById('main-loader');
            if (loader) {
                loader.style.display = show ? 'flex' : 'none';
                loader.setAttribute('aria-busy', show ? 'true' : 'false');

                const loaderText = document.getElementById('loader-text');
                if (loaderText) {
                    loaderText.textContent = message;
                }
            }
            AppState.isLoading = show;
        },

        // Button-level inline loading
        setButtonLoading(buttonId, loading) {
            const button = document.getElementById(buttonId);
            if (!button) return;

            const btnText = button.querySelector('.btn-text');
            const btnSpinner = button.querySelector('.btn-spinner');
            const loadingText = button.dataset.loadingText || 'Loading...';

            if (loading) {
                button.disabled = true;
                if (btnText) {
                    if (!btnText.dataset.original) {
                        btnText.dataset.original = btnText.textContent;
                    }
                    btnText.textContent = loadingText;
                }
                if (btnSpinner) btnSpinner.style.display = 'inline-block';
                button.classList.add('btn-loading');
            } else {
                button.disabled = false;
                if (btnText && btnText.dataset.original) {
                    btnText.textContent = btnText.dataset.original;
                }
                if (btnSpinner) btnSpinner.style.display = 'none';
                button.classList.remove('btn-loading');
            }
        },

        // Store original button text
        initButton(buttonId) {
            const button = document.getElementById(buttonId);
            if (button) {
                const btnText = button.querySelector('.btn-text');
                if (btnText && !button.dataset.originalText) {
                    button.dataset.originalText = btnText.textContent;
                }
            }
        },

        showNotification(message, type = 'info') {
            const container = document.getElementById('notifications') || this.createNotificationContainer();

            const notification = document.createElement('div');
            notification.className = `notification notification-${type}`;
            notification.innerHTML = `
                <span>${message}</span>
                <button class="notification-close" onclick="this.parentElement.remove()">&times;</button>
            `;

            container.appendChild(notification);

            setTimeout(() => {
                notification.classList.add('fade-out');
                setTimeout(() => notification.remove(), 300);
            }, 5000);
        },

        createNotificationContainer() {
            const container = document.createElement('div');
            container.id = 'notifications';
            container.className = 'notifications-container';
            document.body.appendChild(container);
            return container;
        },

        updateProgress(stage, progress) {
            const progressBar = document.querySelector(`[data-stage="${stage}"] .progress-bar`);
            if (progressBar) {
                progressBar.style.width = `${progress}%`;
            }
        },

        scrollToBottom(selector = '#chat-messages') {
            const container = document.querySelector(selector);
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },

        formatFileSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        },

        // Add activity item to feed
        addActivity(message, type = 'info', duration = null) {
            const feed = document.getElementById('activity-feed');
            if (!feed) return;

            const icons = {
                info: 'ℹ️',
                success: '✅',
                error: '❌',
                warning: '⚠️',
                processing: '⏳'
            };

            const item = document.createElement('div');
            item.className = `activity-item ${type}`;
            item.innerHTML = `
                <span class="activity-icon">${icons[type] || icons.info}</span>
                <span class="activity-text">${message}</span>
                <span class="activity-time">${new Date().toLocaleTimeString()}</span>
            `;

            feed.insertBefore(item, feed.firstChild);

            // Auto-remove after duration (if specified)
            if (duration) {
                setTimeout(() => {
                    item.classList.add('fade-out');
                    setTimeout(() => item.remove(), 300);
                }, duration);
            }
        },

        // Clear activity feed
        clearActivity() {
            const feed = document.getElementById('activity-feed');
            if (feed) feed.innerHTML = '';
        },

        // Update activity item status
        updateActivity(index, newType, newMessage) {
            const items = document.querySelectorAll('.activity-item');
            if (items[index]) {
                items[index].className = `activity-item ${newType}`;
                const text = items[index].querySelector('.activity-text');
                const icon = items[index].querySelector('.activity-icon');

                if (text) text.textContent = newMessage;

                const icons = {
                    info: 'ℹ️',
                    success: '✅',
                    error: '❌',
                    warning: '⚠️',
                    processing: '⏳'
                };
                if (icon) icon.textContent = icons[newType] || icons.info;
            }
        }
    };

    // ============================================================================
    // CHAT FUNCTIONALITY
    // ============================================================================

    const Chat = {
        async sendMessage(message) {
            let caseId = AppState.getCaseId();
            if (!caseId) {
                // Create new case if needed
                const newCase = await API.post(`${API_BASE}/case/new`);
                caseId = newCase.case_id;
                AppState.setCaseId(caseId);
            }

            const submitBtn = document.querySelector('.btn-chat-submit');
            const btnText = submitBtn?.querySelector('.btn-text');
            const btnSpinner = submitBtn?.querySelector('.btn-spinner');

            try {
                // Clear input
                const input = document.querySelector('[name="message"]');
                if (input) input.value = '';

                // Show inline loading on button
                if (submitBtn) {
                    submitBtn.disabled = true;
                    if (btnText) {
                        btnText.dataset.original = btnText.textContent;
                        btnText.textContent = 'Sending...';
                    }
                    if (btnSpinner) btnSpinner.style.display = 'inline-block';
                }

                UI.addActivity('Sending message...', 'processing');

                const result = await API.post(
                    `${API_BASE}/case/${caseId}/chat`,
                    { message },
                    true
                );

                // Update UI
                this.renderMessages(result.messages || []);
                this.updateProcedureInfo(result.procedure);

                if (result.missing_fields && result.missing_fields.length === 0) {
                    AppState.setStage('documents');
                    this.showDocumentUploadPrompt();
                }

                UI.scrollToBottom();
                UI.updateActivity(0, 'success', 'Message sent!');
            } catch (error) {
                UI.showNotification(error.message, 'error');
                UI.addActivity(`Failed to send message: ${error.message}`, 'error');
            } finally {
                // Reset button
                if (submitBtn) {
                    submitBtn.disabled = false;
                    if (btnText && btnText.dataset.original) {
                        btnText.textContent = btnText.dataset.original;
                    }
                    if (btnSpinner) btnSpinner.style.display = 'none';
                }
            }
        },

        renderMessages(messages) {
            const container = document.getElementById('chat-messages');
            if (!container) return;

            container.innerHTML = messages.map(msg => `
                <div class="message message-${msg.role}">
                    <div class="message-content">
                        <div class="message-role">${msg.role === 'user' ? 'You' : 'Assistant'}</div>
                        <div class="message-text">${this.formatMessage(msg.content)}</div>
                    </div>
                    <div class="message-time">
                        <small>${msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : ''}</small>
                    </div>
                </div>
            `).join('');
        },

        formatMessage(content) {
            // Simple formatting - convert newlines to breaks
            // Use split/join instead of regex to avoid FastAPI escaping issues
            return content.split('\n').join('<br>');
        },

        updateProcedureInfo(procedure) {
            const container = document.getElementById('procedure-info');
            if (!container || !procedure) return;

            container.innerHTML = `
                <div class="procedure-card">
                    <h4>${procedure.name}</h4>
                    <p>${procedure.rationale || ''}</p>
                    <small>Confidence: ${(procedure.confidence * 100).toFixed(0)}%</small>
                </div>
            `;
        },

        showDocumentUploadPrompt() {
            UI.showNotification('Please upload the required documents to continue.', 'info');
            document.getElementById('upload-section')?.scrollIntoView({ behavior: 'smooth' });
        }
    };

    // ============================================================================
    // DOCUMENT UPLOAD
    // ============================================================================

    const Documents = {
        async uploadFiles(files) {
            console.log('[Documents] uploadFiles called with', files.length, 'files');
            const caseId = AppState.getCaseId();
            console.log('[Documents] caseId:', caseId);
            if (!caseId) {
                UI.showNotification('Please start a conversation first.', 'warning');
                return;
            }

            // Validate files
            const validFiles = this.validateFiles(files);
            console.log('[Documents] validFiles:', validFiles.length);
            if (validFiles.length === 0) return;

            try {
                console.log('[Documents] Starting upload...');
                UI.addActivity(`Uploading ${validFiles.length} file(s)...`, 'processing');

                const result = await API.post(
                    `${API_BASE}/case/${caseId}/docs/upload`,
                    { files: validFiles },
                    true
                );

                console.log('[Documents] Upload result:', result);
                UI.addActivity(`Uploaded ${result.uploaded.length} file(s) successfully!`, 'success');
                UI.showNotification(`Uploaded ${result.uploaded.length} file(s)`, 'success');

                // Auto-run OCR
                console.log('[Documents] Calling runOCR...');
                await this.runOCR();

            } catch (error) {
                console.error('[Documents] Upload error:', error);
                UI.addActivity(`Upload failed: ${error.message}`, 'error');
                UI.showNotification(error.message, 'error');
            }
        },

        validateFiles(files) {
            const valid = [];

            for (const file of files) {
                const ext = '.' + file.name.split('.').pop().toLowerCase();

                if (!ALLOWED_EXTENSIONS.includes(ext)) {
                    UI.showNotification(`Invalid file type: ${file.name}`, 'error');
                    continue;
                }

                if (file.size > MAX_FILE_SIZE) {
                    UI.showNotification(`File too large: ${file.name} (max 20MB)`, 'error');
                    continue;
                }

                valid.push(file);
            }

            return valid;
        },

        async runOCR() {
            try {
                console.log('[Documents] runOCR called');
                UI.initButton('btn-run-ocr');
                UI.setButtonLoading('btn-run-ocr', true);
                UI.addActivity('Starting OCR process... (10-20 seconds)', 'processing');

                const caseId = AppState.getCaseId();
                console.log('[Documents] runOCR caseId:', caseId);
                if (!caseId) {
                    throw new Error('No case ID found. Please start a conversation first.');
                }
                console.log('[Documents] Calling OCR API...');
                await API.post(`${API_BASE}/case}/${caseId}/docs/run_ocr`, {});
                console.log('[Documents] OCR API call complete');

                UI.updateActivity(0, 'success', 'OCR complete!');
                UI.addActivity('Extracting data from documents... (5-15 seconds)', 'processing');

                // Run extraction
                console.log('[Documents] Calling runExtraction...');
                await this.runExtraction();

            } catch (error) {
                console.error('[Documents] OCR error:', error);
                UI.updateActivity(0, 'error', 'OCR failed');
                UI.showNotification(`OCR failed: ${error.message}`, 'error');
                UI.setButtonLoading('btn-run-ocr', false);
            }
        },

        async runExtraction() {
            try {
                UI.initButton('btn-run-extract');
                UI.setButtonLoading('btn-run-extract', true);

                const caseId = AppState.getCaseId();
                if (!caseId) {
                    throw new Error('No case ID found. Please start a conversation first.');
                }
                const result = await API.post(
                    `${API_BASE}/case/${caseId}/docs/extract_validate`,
                    {}
                );

                this.renderExtractions(result.extractions);
                this.renderValidations(result.validations);

                // Move to risk stage
                AppState.setStage('risk');
                UI.addActivity('Documents processed successfully!', 'success');
                UI.showNotification('Documents processed. Ready for risk assessment.', 'success');

                // Auto-run risk assessment
                await Risk.runAssessment();

            } catch (error) {
                UI.addActivity(`Extraction failed: ${error.message}`, 'error');
                UI.showNotification(`Extraction failed: ${error.message}`, 'error');
                UI.setButtonLoading('btn-run-extract', false);
            }
        },

        renderExtractions(extractions) {
            // Update UI with extraction results
            const container = document.getElementById('extractions-container');
            if (!container) return;

            container.innerHTML = extractions.map(ext => `
                <div class="extraction-card">
                    <h5>${ext.doc_type}</h5>
                    <div class="confidence">Confidence: ${(ext.confidence * 100).toFixed(0)}%</div>
                </div>
            `).join('');
        },

        renderValidations(validations) {
            const container = document.getElementById('validations-container');
            if (!container) return;

            container.innerHTML = validations.map(val => `
                <div class="validation-item ${val.passed ? 'pass' : 'fail'}">
                    <span>${val.passed ? '✓' : '✗'}</span>
                    <span>${val.message}</span>
                </div>
            `).join('');
        }
    };

    // ============================================================================
    // RISK ASSESSMENT
    // ============================================================================

    const Risk = {
        async runAssessment() {
            const caseId = AppState.getCaseId();
            if (!caseId) return;

            try {
                UI.initButton('btn-run-risk');
                UI.setButtonLoading('btn-run-risk', true);
                UI.addActivity('Analyzing risk... (10-30 seconds)', 'processing');

                const result = await API.post(`${API_BASE}/case/${caseId}/risk/run`, {});

                this.renderResult(result);
                UI.addActivity('Risk assessment complete!', 'success');
                UI.showNotification('Risk assessment complete', 'success');

            } catch (error) {
                UI.addActivity(`Risk assessment failed: ${error.message}`, 'error');
                UI.showNotification(`Risk assessment failed: ${error.message}`, 'error');
            } finally {
                UI.setButtonLoading('btn-run-risk', false);
            }
        },

        renderResult(result) {
            // Update risk gauge
            const gauge = document.querySelector('.risk-gauge-fill');
            const scoreValue = document.querySelector('.score-value');
            if (gauge) {
                gauge.style.width = `${result.score}%`;
                gauge.setAttribute('data-level', result.level);
            }
            if (scoreValue) {
                scoreValue.textContent = result.score;
            }

            // Update risk level badge
            const badge = document.querySelector('.risk-badge');
            if (badge) {
                badge.textContent = result.level;
                badge.className = `risk-badge risk-${result.level.toLowerCase()}`;
            }

            // Render factors
            this.renderFactors(result.factors || []);

            // Render explanation
            this.renderExplanation(result.explanation || {});
        },

        renderFactors(factors) {
            const container = document.getElementById('risk-factors');
            if (!container) return;

            container.innerHTML = factors.map(factor => `
                <div class="factor-item">
                    <span class="factor-id">[${factor.factor_id}]</span>
                    <span class="factor-points">+${factor.points_added}</span>
                    <div class="factor-description">${factor.description}</div>
                </div>
            `).join('');
        },

        renderExplanation(explanation) {
            const container = document.getElementById('risk-explanation');
            if (!container) return;

            container.innerHTML = `
                ${explanation.executive_summary ? `<p>${explanation.executive_summary}</p>` : ''}
                ${explanation.explanation_bullets ? `
                    <ul>
                        ${explanation.explanation_bullets.map(b => `<li>${b}</li>`).join('')}
                    </ul>
                ` : ''}
            `;
        }
    };

    // ============================================================================
    // EVENT LISTENERS
    // ============================================================================

    function initEventListeners() {
        // Initialize button states
        UI.initButton('btn-run-ocr');
        UI.initButton('btn-run-extract');
        UI.initButton('btn-run-risk');

        // File input and upload button
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            console.log('[App] Found file-input element, attaching listeners');

            fileInput.addEventListener('change', (e) => {
                console.log('[App] File input changed, files:', e.target.files.length);
                if (e.target.files.length > 0) {
                    Documents.uploadFiles(e.target.files);
                }
            });

            // Make the submit button trigger the file input
            const uploadForm = fileInput.closest('form');
            if (uploadForm) {
                const submitBtn = uploadForm.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        console.log('[App] Upload button clicked, triggering file picker');
                        fileInput.click();
                    });
                }
            }
        } else {
            console.warn('[App] file-input element not found!');
        }

        // Drag and drop
        const dropZone = document.getElementById('upload-zone');
        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('dragover');
            });

            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('dragover');
            });

            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    Documents.uploadFiles(e.dataTransfer.files);
                }
            });
        }

        // Chat form
        const chatForm = document.getElementById('chat-form');
        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const input = chatForm.querySelector('input[name="message"]');
                if (input && input.value.trim()) {
                    Chat.sendMessage(input.value.trim());
                }
            });
        }

        // OCR button
        const ocrButton = document.getElementById('btn-run-ocr');
        if (ocrButton) {
            ocrButton.addEventListener('click', () => Documents.runOCR());
        }

        // Extraction button
        const extractButton = document.getElementById('btn-run-extract');
        if (extractButton) {
            extractButton.addEventListener('click', () => Documents.runExtraction());
        }

        // Risk assessment button (support both old and new IDs)
        const riskButton = document.getElementById('btn-run-risk') || document.getElementById('run-risk-btn');
        if (riskButton) {
            riskButton.addEventListener('click', () => Risk.runAssessment());
        }

        // New case button
        const newCaseButton = document.getElementById('new-case-btn');
        if (newCaseButton) {
            newCaseButton.addEventListener('click', () => {
                sessionStorage.removeItem('caseId');
                window.location.href = '/ui';
            });
        }
    }

    // ============================================================================
    // INITIALIZATION
    // ============================================================================

    function init() {
        // Load case ID from URL or session storage
        const urlPattern = new RegExp('/ui/case/([a-zA-Z0-9-]+)');
        const pathMatch = window.location.pathname.match(urlPattern);
        if (pathMatch) {
            AppState.setCaseId(pathMatch[1]);
        } else if (AppState.getCaseId()) {
            AppState.updateURL();
        }

        // Initialize event listeners
        initEventListeners();

        // Set initial stage
        AppState.updateStageIndicators();

        // Expose to global scope for HTMX/onclick handlers
        window.App = {
            Chat,
            Documents,
            Risk,
            UI,
            State: AppState
        };

        console.log('Case-to-Clearance app initialized');
    }

    // Run initialization when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
