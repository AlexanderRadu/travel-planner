// static/js/point-photos-fix.js
class PointPhotosManager {
    constructor() {
        this.existingPhotos = [];
        this.deletedPhotoIds = [];
        this.newPhotoFiles = [];
        this.currentPointIndex = null;
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        document.addEventListener('show.bs.modal', (event) => {
            if (event.target.id === 'point-editor-modal') {
                this.onPointModalOpen();
            }
        });
        
        document.addEventListener('hidden.bs.modal', (event) => {
            if (event.target.id === 'point-editor-modal') {
                this.onPointModalClose();
            }
        });
        
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
        const pointIndexInput = document.getElementById('edit-point-index');
        if (!pointIndexInput) return;
        
        this.currentPointIndex = parseInt(pointIndexInput.value);
        if (isNaN(this.currentPointIndex)) return;
        
        if (!window.routeEditor || !window.routeEditor.points) return;
        const point = window.routeEditor.points[this.currentPointIndex];
        if (!point) return;
        
        this.existingPhotos = point.photos ? [...point.photos] : [];
        this.deletedPhotoIds = [];
        this.newPhotoFiles = [];
        
        console.log('PointPhotosManager: Открыта точка', this.currentPointIndex, 'с фото:', this.existingPhotos);
        
        this.loadPhotosIntoModal();
    }
    
    onPointModalClose() {
        this.existingPhotos = [];
        this.deletedPhotoIds = [];
        this.newPhotoFiles = [];
        this.currentPointIndex = null;
        
        this.clearModalPhotos();
    }
    
    loadPhotosIntoModal() {
        this.clearModalPhotos();
        
        if (this.existingPhotos.length > 0) {
            const mainPhoto = this.existingPhotos[0];
            this.loadMainPhoto(mainPhoto);
        }
        
        if (this.existingPhotos.length > 1) {
            const additionalPhotos = this.existingPhotos.slice(1);
            this.loadAdditionalPhotos(additionalPhotos);
        }
        
        this.updatePhotoCount();
    }
    
    loadMainPhoto(photoData) {
        const uploadSection = document.querySelector('#point-editor-modal .main-photo-upload');
        if (!uploadSection) return;
        
        const preview = uploadSection.querySelector('.main-photo-preview');
        const placeholder = uploadSection.querySelector('.h-100');
        const img = preview?.querySelector('img');
        
        if (!preview || !img) return;
        
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
        
        const uploadButton = grid.querySelector('.additional-photo-upload');
        if (uploadButton) uploadButton.remove();
        
        photos.forEach((photoData, index) => {
            let photoUrl = photoData;
            if (typeof photoData === 'object' && photoData.url) {
                photoUrl = photoData.url;
            }
            
            const photoItem = this.createExistingPhotoItem(photoUrl, index + 1);
            grid.appendChild(photoItem);
        });
        
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
        if (photoIndex === 0) {
            this.removeMainPhoto();
        } else {
            const actualIndex = photoIndex - 1;
            if (this.existingPhotos[photoIndex]) {
                this.deletedPhotoIds.push(photoIndex);
                
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
        
        if (this.existingPhotos.length > 0) {
            this.deletedPhotoIds.push(0);
        }
        
        this.updatePhotoCount();
    }
    
    clearModalPhotos() {
        const uploadSection = document.querySelector('#point-editor-modal .main-photo-upload');
        if (uploadSection) {
            const preview = uploadSection.querySelector('.main-photo-preview');
            const placeholder = uploadSection.querySelector('.h-100');
            if (preview) preview.style.display = 'none';
            if (placeholder) placeholder.style.display = 'flex';
        }
        
        const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
        if (grid) {
            grid.innerHTML = '<div class="additional-photo-upload border rounded bg-light d-flex align-items-center justify-content-center" style="height: 80px; cursor: pointer; aspect-ratio: 1;"><i class="fas fa-plus text-muted"></i></div>';
        }
    }
    
    updatePhotoCount() {
        const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
        const countElement = document.getElementById('additional-photos-count');
        if (!grid || !countElement) return;
        
        const existingItems = grid.querySelectorAll('.additional-photo-item[data-is-existing="true"]');
        const existingCount = existingItems.length;
        
        const newItems = grid.querySelectorAll('.additional-photo-item[data-is-existing="false"]');
        const newCount = newItems.length;
        
        const totalCount = existingCount + newCount;
        countElement.textContent = `${totalCount}/4`;
    }
    
    handleSavePoint() {
        if (this.currentPointIndex === null || !window.routeEditor) return;
        
        const allPhotos = this.collectAllPhotos();
        
        console.log('PointPhotosManager: Сохранение точки', this.currentPointIndex, 'с фото:', allPhotos.length);
        
        const point = window.routeEditor.points[this.currentPointIndex];
        if (point) {
            point.photos = allPhotos;
            
            if (typeof window.routeEditor.savePoint === 'function') {
                document.removeEventListener('click', this.saveHandler);
                window.routeEditor.savePoint();
                setTimeout(() => {
                    this.initEventListeners();
                }, 100);
            }
        }
    }
    
    collectAllPhotos() {
        const allPhotos = [];
        
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
        
        for (let i = 1; i < this.existingPhotos.length; i++) {
            if (!this.deletedPhotoIds.includes(i)) {
                allPhotos.push(this.existingPhotos[i]);
            }
        }
        
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

let pointPhotosManager;

document.addEventListener('DOMContentLoaded', function() {
    pointPhotosManager = new PointPhotosManager();
    
    overridePhotoHandlers();
});

function overridePhotoHandlers() {
    const additionalUpload = document.querySelector('#point-editor-modal .additional-photo-upload');
    if (additionalUpload) {
        additionalUpload.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.accept = 'image/*';
            
            input.onchange = function(event) {
                if (!event.target.files || event.target.files.length === 0) return;
                
                const grid = document.querySelector('#point-editor-modal .additional-photos-grid');
                if (!grid) return;
                
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