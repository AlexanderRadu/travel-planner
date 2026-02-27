// static/js/audio_generation.js
class AudioGenerationManager {
    constructor() {
        this.currentPointId = null;
        this.currentPointIndex = null;
        this.audioUrl = null;
        this.isGenerating = false;
        this.audioElement = null;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupAudioElement();
    }

    setupEventListeners() {
        document.getElementById('use-description-text')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.useDescriptionText();
        });

        document.getElementById('generate-ai-audio')?.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.generateAudio();
        });

        document.getElementById('retry-ai-generation')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.generateAudio();
        });

        document.getElementById('point-description')?.addEventListener('input', () => {
            this.syncDescriptionToPreview();
        });

        document.getElementById('re-record-audio')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.resetAudio();
        });

        document.getElementById('remove-audio')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.removeAudio();
        });

        document.getElementById('enable-audio-guide')?.addEventListener('change', (e) => {
            this.handleAudioToggle(e.target.checked);
        });
    }

    setupAudioElement() {
        if (!document.getElementById('audio-player-element')) {
            this.audioElement = document.createElement('audio');
            this.audioElement.id = 'audio-player-element';
            this.audioElement.style.display = 'none';
            document.body.appendChild(this.audioElement);
        } else {
            this.audioElement = document.getElementById('audio-player-element');
        }
    }

    setupForPoint(pointId, pointIndex, pointData = null) {
        this.currentPointId = pointId;
        this.currentPointIndex = pointIndex;
        
        this.resetGenerationUI();
        
        if (pointData?.description) {
            const preview = document.getElementById('ai-text-preview');
            if (preview) {
                preview.textContent = pointData.description;
            }
        } else {
            this.syncDescriptionToPreview();
        }
        
        if (pointData?.audio_url) {
            this.showAudioPlayer(pointData.audio_url, pointData.audio_filename || 'Point audio guide');
        }
        
        this.hideGenerationProgress();
        this.hideGenerationError();
        this.hideGenerationSuccess();
    }

    useDescriptionText() {
        const descriptionField = document.getElementById('point-description');
        const preview = document.getElementById('ai-text-preview');
        
        if (descriptionField && preview) {
            const desc = descriptionField.value.trim();
            if (desc) {
                preview.textContent = desc;
                this.showToast('Text loaded into generation area', 'info'); // Текст загружен в область генерации
            } else {
                this.showToast('Point description is empty', 'warning'); // Описание точки пустое
            }
        }
    }

    syncDescriptionToPreview() {
        const descriptionField = document.getElementById('point-description');
        const preview = document.getElementById('ai-text-preview');
        
        if (descriptionField && preview) {
            const desc = descriptionField.value.trim();
            if (desc && (!preview.textContent || preview.textContent.trim() === '')) {
                preview.textContent = desc;
            }
        }
    }

    async generateAudio() {
        if (!this.currentPointId || this.currentPointId <= 0) {
            this.showToast('Save the point first, then generate audio', 'warning'); // Сначала сохраните точку, затем сгенерируйте аудио
            return;
        }

        const text = document.getElementById('ai-text-preview')?.textContent.trim();
        if (!text) {
            this.showToast('Generation text is empty', 'warning'); // Текст для генерации пуст
            return;
        }

        if (text.length > 5000) {
            this.showToast('Text is too long (max 5000 characters)', 'warning'); // Текст слишком длинный (максимум 5000 символов)
            return;
        }

        if (this.isGenerating) {
            return;
        }

        this.isGenerating = true;
        this.showGenerationProgress();

        try {
            const voice = document.getElementById('ai-voice-select')?.value || 'alloy';
            const language = document.getElementById('ai-language-select')?.value || 'ru-RU';
            const csrfToken = this.getCsrfToken();

            const response = await fetch(`/api/ai-audio/generate/${this.currentPointId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    text: text,
                    voice_type: voice,
                    language: language
                })
            });

            const data = await response.json();
            
            if (response.ok && data.status === 'success') {
                this.audioUrl = data.audio_url;
                const filename = `AI-audio-guide_${new Date().toLocaleDateString('ru-RU')}.mp3`;
                
                this.showAudioPlayer(data.audio_url, filename);
                this.showGenerationSuccess();
                
                if (window.routeEditor?.updatePointAudio) {
                    window.routeEditor.updatePointAudio(this.currentPointId, data.audio_url, filename);
                }
                
                this.showToast('✅ Audio guide successfully generated!', 'success'); // ✅ Аудиогид успешно сгенерирован!
            } else {
                throw new Error(data.error || 'Server error');
            }
        } catch (error) {
            this.showGenerationError(error.message || 'Unknown error');
            this.showToast(`Audio generation failed: ${error.message}`, 'danger'); // Ошибка генерации: ...
        } finally {
            this.isGenerating = false;
            this.hideGenerationProgress();
        }
    }

    showAudioPlayer(audioUrl, filename = 'Point audio guide') {
        document.getElementById('point-audio-player').style.display = 'block';
        document.getElementById('point-audio-recorder').style.display = 'none';
        
        document.getElementById('audio-filename').textContent = filename;
        
        document.getElementById('enable-audio-guide').checked = true;
        
        if (this.audioElement) {
            this.audioElement.src = audioUrl;
            this.setupAudioPlayerControls();
        }
        
        this.showAudioControls();
    }

    setupAudioPlayerControls() {
        if (!this.audioElement) return;
        
        const playBtn = document.querySelector('.audio-play-btn');
        const progressBar = document.querySelector('.audio-progress');
        const durationSpan = document.querySelector('.audio-duration');
        
        if (!playBtn) return;
        
        const formatTime = (seconds) => {
            if (isNaN(seconds)) return '0:00';
            const mins = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${mins}:${secs.toString().padStart(2, '0')}`;
        };
        
        const newPlayBtn = playBtn.cloneNode(true);
        playBtn.parentNode.replaceChild(newPlayBtn, playBtn);
        
        newPlayBtn.addEventListener('click', () => {
            if (this.audioElement.paused) {
                this.audioElement.play().catch(e => {
                    this.showToast('Audio playback error', 'danger'); // Ошибка воспроизведения аудио
                });
                newPlayBtn.innerHTML = '<i class="fas fa-pause"></i>';
            } else {
                this.audioElement.pause();
                newPlayBtn.innerHTML = '<i class="fas fa-play"></i>';
            }
        });
        
        this.audioElement.addEventListener('timeupdate', () => {
            if (this.audioElement.duration && progressBar) {
                const progress = (this.audioElement.currentTime / this.audioElement.duration) * 100;
                progressBar.style.width = `${progress}%`;
            }
            if (durationSpan) {
                durationSpan.textContent = formatTime(this.audioElement.currentTime);
            }
        });
        
        this.audioElement.addEventListener('ended', () => {
            newPlayBtn.innerHTML = '<i class="fas fa-play"></i>';
            if (progressBar) progressBar.style.width = '0%';
            if (durationSpan) durationSpan.textContent = '0:00';
        });
        
        this.audioElement.addEventListener('loadedmetadata', () => {
            if (durationSpan) {
                durationSpan.textContent = formatTime(this.audioElement.duration);
            }
        });
        
        this.audioElement.addEventListener('error', (e) => {
            this.showToast('Audio file failed to load', 'danger');
        });
    }

    showAudioControls() {
        const controls = document.querySelectorAll('#re-record-audio, #remove-audio');
        controls.forEach(control => {
            control.style.display = 'inline-block';
        });
    }

    hideAudioControls() {
        const controls = document.querySelectorAll('#re-record-audio, #remove-audio');
        controls.forEach(control => {
            control.style.display = 'none';
        });
    }

    resetAudio() {
        if (confirm('Are you sure you want to re-record the audio?')) {
            this.audioUrl = null;
            if (this.audioElement) {
                this.audioElement.src = '';
                this.audioElement.pause();
            }
            
            document.getElementById('point-audio-player').style.display = 'none';
            document.getElementById('point-audio-recorder').style.display = 'block';
            
            document.getElementById('enable-audio-guide').checked = false;
            
            this.resetGenerationUI();
            
            this.showToast('Audio reset. You can record a new one.', 'info');
        }
    }

    removeAudio() {
        if (confirm('Are you sure you want to delete the audio?')) {
            this.audioUrl = null;
            if (this.audioElement) {
                this.audioElement.src = '';
                this.audioElement.pause();
            }
            
            document.getElementById('point-audio-player').style.display = 'none';
            document.getElementById('point-audio-recorder').style.display = 'block';
            
            document.getElementById('enable-audio-guide').checked = false;
            
            this.resetGenerationUI();
            
            if (window.routeEditor?.updatePointAudio) {
                window.routeEditor.updatePointAudio(this.currentPointId, null);
            }
            
            this.showToast('Audio deleted', 'info');
        }
    }

    handleAudioToggle(isEnabled) {
        if (!isEnabled && this.audioUrl) {
            if (confirm('Disabling audio will hide the player. Continue?')) {
                document.getElementById('point-audio-player').style.display = 'none';
                document.getElementById('point-audio-recorder').style.display = 'block';
            } else {
                document.getElementById('enable-audio-guide').checked = true;
            }
        } else if (isEnabled && !this.audioUrl) {
            document.getElementById('point-audio-player').style.display = 'none';
            document.getElementById('point-audio-recorder').style.display = 'block';
        }
    }

    resetGenerationUI() {
        this.hideGenerationProgress();
        this.hideGenerationError();
        this.hideGenerationSuccess();
        const generateBtn = document.getElementById('generate-ai-audio');
        if (generateBtn) generateBtn.disabled = false;
    }

    showGenerationProgress() {
        const progressEl = document.getElementById('ai-generation-progress');
        const generateBtn = document.getElementById('generate-ai-audio');
        if (progressEl) progressEl.style.display = 'block';
        if (generateBtn) generateBtn.disabled = true;
        
        this.hideGenerationError();
        this.hideGenerationSuccess();
    }

    hideGenerationProgress() {
        const progressEl = document.getElementById('ai-generation-progress');
        if (progressEl) progressEl.style.display = 'none';
    }

    showGenerationError(errorMessage) {
        const errorEl = document.getElementById('ai-generation-error');
        const errorMsg = document.getElementById('ai-error-message');
        const generateBtn = document.getElementById('generate-ai-audio');
        
        if (errorEl && errorMsg) {
            errorMsg.textContent = errorMessage;
            errorEl.style.display = 'block';
        }
        if (generateBtn) generateBtn.disabled = false;
        
        this.hideGenerationProgress();
        this.hideGenerationSuccess();
    }

    hideGenerationError() {
        const errorEl = document.getElementById('ai-generation-error');
        if (errorEl) errorEl.style.display = 'none';
    }

    showGenerationSuccess() {
        const successEl = document.getElementById('ai-generation-success');
        if (successEl) successEl.style.display = 'block';
        
        this.hideGenerationProgress();
        this.hideGenerationError();
    }

    hideGenerationSuccess() {
        const successEl = document.getElementById('ai-generation-success');
        if (successEl) successEl.style.display = 'none';
    }

    getCsrfToken() {
        const tokenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (tokenInput) {
            return tokenInput.value;
        }
        
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    showToast(message, type = 'info') {
        if (window.routeEditor && typeof window.routeEditor.showToast === 'function') {
            window.routeEditor.showToast(message, type);
        } else {
            const toast = document.createElement('div');
            toast.className = `toast align-items-center text-white bg-${type} border-0 position-fixed bottom-0 end-0 m-3`;
            toast.setAttribute('role', 'alert');
            toast.style.zIndex = '9999';
            toast.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            `;
            document.body.appendChild(toast);
            
            const bsToast = new bootstrap.Toast(toast);
            bsToast.show();
            
            setTimeout(() => {
                toast.remove();
            }, 3000);
        }
    }
}

window.audioGenerationManager = new AudioGenerationManager();

window.setupPointAudio = function(pointId, pointIndex, pointData) {
    if (window.audioGenerationManager) {
        window.audioGenerationManager.setupForPoint(pointId, pointIndex, pointData);
    }
};

document.addEventListener('DOMContentLoaded', () => {});