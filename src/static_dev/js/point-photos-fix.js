// static/js/point-photos-fix.js
class PointPhotosManager {
    constructor() {
        // Храним данные о фото для текущей редактируемой точки
        this.existingPhotos = []; // Существующие фото
        this.deletedPhotoIds = []; // ID удаленных фото
        this.newPhotoFiles = []; // Новые загруженные файлы
        this.currentPointIndex = null;
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // Обработчик открытия модального окна редактирования точки
        document.addEventListener('show.bs.modal', (event) => {
            if (event.target.id === 'point-editor-modal') {
                this.onPointModalOpen();
            }
        });
        
        // Обработчик закрытия модального окна
        document.addEventListener('hidden.bs.modal', (event) => {
            if (event.target.id === 'point-editor-modal') {
                this.onPointModalClose();
            }
        });
        
        // Перехватываем клик по кнопке сохранения точки
        document.addEventListener('click', (e) => {
            if (e.target.id === 'save-point-btn' || 
                (e.target.closest && e.target.closest('#save-point-btn'))) {
                e.preventDefault();
                e.stopPropagation();
                this.handleSavePoint();
            }
        });
    }
    
    onPointModalOpen() {
        // Получаем индекс редактируемой точки
        const pointIndexInput = document.getElementById('edit-point-index');
        if (!pointIndexInput) return;
        
        this.currentPointIndex = parseInt(pointIndexInput.value);
        if (isNaN(this.currentPointIndex)) return;
        
        // Получаем точку из routeEditor
        if (!window.routeEditor || !window.routeEditor.points) return;
        const point = window.routeEditor.points[this.currentPointIndex];
        if (!point) return;
        
        // Сохраняем существующие фото
        this.existingPhotos = point.photos ? [...point.photos] : [];
        this.deletedPhotoIds = [];
        this.newPhotoFiles = [];
        
        console.log('PointPhotosManager: Открыта точка', this.currentPointIndex, 'с фото:', this.existingPhotos);
        
        // Загружаем существующие фото в модальное окно
        this.loadPhotosIntoModal();
    }
    
    onPointModalClose() {
        // Очищаем временные данные
        this.existingPhotos = [];
        this.deletedPhotoIds = [];
        this.newPhotoFiles = [];
        this.currentPointIndex = null;
        
        // Очищаем фото в модальном окне
        this.clearModalPhotos();
    }
    
    loadPhotosIntoModal() {
        // Очищаем текущие фото в модальном окне
        this.clearModalPhotos();
        
        // Загружаем основное фото
        if (this.existingPhotos.length > 0) {
            const mainPhoto = this.existingPhotos[0];
            this.loadMainPhoto(mainPhoto);
        }
        
        // Загружаем дополнительные фото
        if (this.existingPhotos.length > 1) {
            const additionalPhotos = this.existingPhotos.slice(1);
            this.loadAdditionalPhotos(additionalPhotos);
        }
        
        // Обновляем счетчик
        this.updatePhotoCount();
    }
    
    loadMainPhoto(photoData) {
        const uploadSection = document.querySelector('#point-editor-modal .main-photo-upload');
        if (!uploadSection) return;
        
        const preview = uploadSection.querySelector('.main-photo-preview');
        const placeholder = uploadSection.querySelector('.h-100');
        const img = preview?.querySelector('img');
        
        if (!preview || !img) return;
        
        // Получаем URL фото (может быть data URL или обычный URL)
        let photoUrl = photoData;
        if (typeof photoData === 'object' && photoData.url) {
            photoUrl = photoData.url;
        }
        
        img.src = photoUrl;
        if (placeholder) placeholder.style.display = 'none';
        preview.style.display = 'block';
    }
    
    loadAdditionalPhotos(photos) {
        const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
        if (!grid) return;
        
        // Удаляем кнопку загрузки временно
        const uploadButton = grid.querySelector('.additional-photo-upload');
        if (uploadButton) uploadButton.remove();
        
        // Добавляем каждое фото
        photos.forEach((photoData, index) => {
            let photoUrl = photoData;
            if (typeof photoData === 'object' && photoData.url) {
                photoUrl = photoData.url;
            }
            
            const photoItem = this.createExistingPhotoItem(photoUrl, index + 1); // +1 потому что первое фото основное
            grid.appendChild(photoItem);
        });
        
        // Возвращаем кнопку загрузки
        if (uploadButton) {
            grid.appendChild(uploadButton);
        }
    }
    
    createExistingPhotoItem(photoUrl, index) {
        const div = document.createElement('div');
        div.className = 'additional-photo-item';
        div.dataset.photoIndex = index;
        div.dataset.isExisting = 'true';
        
        div.innerHTML = `
            <img src="${photoUrl}" class="w-100 h-100 object-fit-cover rounded">
            <button type="button" class="btn btn-sm btn-danger photo-remove-btn position-absolute top-0 end-0 m-1"
                    style="width: 20px; height: 20px; padding: 0; display: flex; align-items: center; justify-content: center;"
                    onclick="pointPhotosManager.removeExistingPhoto(${index})">
                <i class="fas fa-times" style="font-size: 10px;"></i>
            </button>
        `;
        
        return div;
    }
    
    removeExistingPhoto(photoIndex) {
        // Индекс 0 - основное фото, >0 - дополнительные
        if (photoIndex === 0) {
            // Удаляем основное фото
            this.removeMainPhoto();
        } else {
            // Удаляем дополнительное фото
            const actualIndex = photoIndex - 1; // -1 потому что первый индекс был для основного фото
            if (this.existingPhotos[photoIndex]) {
                this.deletedPhotoIds.push(photoIndex);
                
                // Удаляем элемент из DOM
                const photoItem = document.querySelector(`[data-photo-index="${photoIndex}"][data-is-existing="true"]`);
                if (photoItem) {
                    photoItem.remove();
                }
            }
        }
        
        this.updatePhotoCount();
    }
    
    removeMainPhoto() {
        const uploadSection = document.querySelector('#point-editor-modal .main-photo-upload');
        if (!uploadSection) return;
        
        const preview = uploadSection.querySelector('.main-photo-preview');
        const placeholder = uploadSection.querySelector('.h-100');
        
        if (preview) preview.style.display = 'none';
        if (placeholder) placeholder.style.display = 'flex';
        
        // Помечаем основное фото как удаленное
        if (this.existingPhotos.length > 0) {
            this.deletedPhotoIds.push(0);
        }
        
        this.updatePhotoCount();
    }
    
    clearModalPhotos() {
        // Очищаем основное фото
        const uploadSection = document.querySelector('#point-editor-modal .main-photo-upload');
        if (uploadSection) {
            const preview = uploadSection.querySelector('.main-photo-preview');
            const placeholder = uploadSection.querySelector('.h-100');
            if (preview) preview.style.display = 'none';
            if (placeholder) placeholder.style.display = 'flex';
        }
        
        // Очищаем дополнительные фото
        const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
        if (grid) {
            // Оставляем только кнопку загрузки
            grid.innerHTML = '<div class="additional-photo-upload border rounded bg-light d-flex align-items-center justify-content-center" style="height: 80px; cursor: pointer; aspect-ratio: 1;"><i class="fas fa-plus text-muted"></i></div>';
        }
    }
    
    updatePhotoCount() {
        const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
        const countElement = document.getElementById('additional-photos-count');
        if (!grid || !countElement) return;
        
        // Считаем существующие фото которые не удалены
        const existingItems = grid.querySelectorAll('.additional-photo-item[data-is-existing="true"]');
        const existingCount = existingItems.length;
        
        // Считаем новые фото
        const newItems = grid.querySelectorAll('.additional-photo-item[data-is-existing="false"]');
        const newCount = newItems.length;
        
        const totalCount = existingCount + newCount;
        countElement.textContent = `${totalCount}/4`;
    }
    
    handleSavePoint() {
        if (this.currentPointIndex === null || !window.routeEditor) return;
        
        // Собираем все фото
        const allPhotos = this.collectAllPhotos();
        
        console.log('PointPhotosManager: Сохранение точки', this.currentPointIndex, 'с фото:', allPhotos.length);
        
        // Обновляем фото в точке routeEditor
        const point = window.routeEditor.points[this.currentPointIndex];
        if (point) {
            point.photos = allPhotos;
            
            // Вызываем оригинальный savePoint из routeEditor
            if (typeof window.routeEditor.savePoint === 'function') {
                // Временно отключаем наш обработчик, чтобы вызвать оригинальный
                document.removeEventListener('click', this.saveHandler);
                window.routeEditor.savePoint();
                // После сохранения снова вешаем обработчик
                setTimeout(() => {
                    this.initEventListeners();
                }, 100);
            }
        }
    }
    
    collectAllPhotos() {
        const allPhotos = [];
        
        // 1. Основное фото (если не удалено)
        const mainPreview = document.querySelector('#point-editor-modal .main-photo-preview img');
        if (mainPreview && mainPreview.src && 
            !mainPreview.src.includes('data:image/svg') && 
            !this.deletedPhotoIds.includes(0)) {
            
            if (this.existingPhotos[0] && typeof this.existingPhotos[0] === 'object') {
                allPhotos.push(this.existingPhotos[0]);
            } else {
                allPhotos.push(mainPreview.src);
            }
        }
        
        // 2. Существующие дополнительные фото которые не удалены
        for (let i = 1; i < this.existingPhotos.length; i++) {
            if (!this.deletedPhotoIds.includes(i)) {
                allPhotos.push(this.existingPhotos[i]);
            }
        }
        
        // 3. Новые фото из DOM
        const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
        if (grid) {
            const newItems = grid.querySelectorAll('.additional-photo-item[data-is-existing="false"]');
            newItems.forEach(item => {
                const img = item.querySelector('img');
                if (img && img.src) {
                    allPhotos.push(img.src);
                }
            });
        }
        
        return allPhotos;
    }
}

// Глобальный экземпляр
let pointPhotosManager;

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    pointPhotosManager = new PointPhotosManager();
    
    // Переопределяем обработчики загрузки фото
    overridePhotoHandlers();
});

function overridePhotoHandlers() {
    // Перехватываем клик по кнопке загрузки дополнительных фото
    const additionalUpload = document.querySelector('#point-editor-modal .additional-photo-upload');
    if (additionalUpload) {
        additionalUpload.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Создаем временный input
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.accept = 'image/*';
            
            input.onchange = function(event) {
                if (!event.target.files || event.target.files.length === 0) return;
                
                const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
                if (!grid) return;
                
                // Проверяем лимит фото
                const currentCount = grid.querySelectorAll('.additional-photo-item').length;
                if (currentCount + event.target.files.length > 4) {
                    alert('Максимум можно загрузить 4 дополнительных фото');
                    return;
                }
                
                const uploadButton = grid.querySelector('.additional-photo-upload');
                
                Array.from(event.target.files).forEach(file => {
                    if (!file.type.startsWith('image/')) {
                        alert('Пожалуйста, выбирайте только изображения');
                        return;
                    }
                    
                    if (file.size > 5 * 1024 * 1024) {
                        alert('Размер файла не должен превышать 5MB');
                        return;
                    }
                    
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const photoItem = createNewPhotoItem(e.target.result);
                        
                        if (uploadButton) {
                            grid.insertBefore(photoItem, uploadButton);
                        } else {
                            grid.appendChild(photoItem);
                        }
                        
                        pointPhotosManager.updatePhotoCount();
                    };
                    reader.readAsDataURL(file);
                });
            };
            
            input.click();
        };
    }
    
    // Перехватываем клик по основному фото
    const mainPhotoUpload = document.querySelector('#point-editor-modal .main-photo-upload');
    if (mainPhotoUpload) {
        mainPhotoUpload.onclick = function(e) {
            if (e.target.closest('.photo-remove-btn')) return;
            
            e.preventDefault();
            e.stopPropagation();
            
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'image/*';
            
            input.onchange = function(event) {
                if (!event.target.files || event.target.files.length === 0) return;
                
                const file = event.target.files[0];
                if (!file.type.startsWith('image/')) {
                    alert('Пожалуйста, выбирайте только изображения');
                    return;
                }
                
                if (file.size > 5 * 1024 * 1024) {
                    alert('Размер файла не должен превышать 5MB');
                    return;
                }
                
                const reader = new FileReader();
                reader.onload = function(e) {
                    const uploadSection = document.querySelector('#point-editor-modal .main-photo-upload');
                    if (!uploadSection) return;
                    
                    const preview = uploadSection.querySelector('.main-photo-preview');
                    const placeholder = uploadSection.querySelector('.h-100');
                    const img = preview?.querySelector('img');
                    
                    if (placeholder) placeholder.style.display = 'none';
                    if (preview && img) {
                        img.src = e.target.result;
                        preview.style.display = 'block';
                    }
                    
                    // Убираем пометку "удалено" если основное фото было удалено ранее
                    const deleteIndex = pointPhotosManager.deletedPhotoIds.indexOf(0);
                    if (deleteIndex !== -1) {
                        pointPhotosManager.deletedPhotoIds.splice(deleteIndex, 1);
                    }
                };
                reader.readAsDataURL(file);
            };
            
            input.click();
        };
    }
}

function createNewPhotoItem(src) {
    const div = document.createElement('div');
    div.className = 'additional-photo-item';
    div.dataset.isExisting = 'false';
    div.dataset.fileId = Date.now();
    
    div.innerHTML = `
        <img src="${src}" class="w-100 h-100 object-fit-cover rounded">
        <button type="button" class="btn btn-sm btn-danger photo-remove-btn position-absolute top-0 end-0 m-1"
                style="width: 20px; height: 20px; padding: 0; display: flex; align-items: center; justify-content: center;"
                onclick="removeNewPhoto(this)">
            <i class="fas fa-times" style="font-size: 10px;"></i>
        </button>
    `;
    
    return div;
}

function removeNewPhoto(button) {
    const photoItem = button.closest('.additional-photo-item');
    if (photoItem) {
        photoItem.remove();
        if (pointPhotosManager) {
            pointPhotosManager.updatePhotoCount();
        }
    }
}