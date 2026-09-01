(() => {
    const lightbox = document.getElementById('image-lightbox');
    const lightboxImage = document.getElementById('lightbox-image');

    if (!lightbox || !lightboxImage) {
        return;
    }

    const closeButton = lightbox.querySelector('.lightbox__close');
    let lastFocusedElement = null;

    function openLightbox(trigger) {
        const imageUrl = trigger.dataset.lightboxImage;
        const imageAlt = trigger.dataset.lightboxAlt || 'Изображение';

        if (!imageUrl) {
            return;
        }

        lastFocusedElement = document.activeElement;
        lightboxImage.src = imageUrl;
        lightboxImage.alt = imageAlt;
        lightbox.classList.add('is-open');
        lightbox.setAttribute('aria-hidden', 'false');
        document.body.classList.add('lightbox-open');

        closeButton?.focus();
    }

    function closeLightbox() {
        if (!lightbox.classList.contains('is-open')) {
            return;
        }

        lightbox.classList.remove('is-open');
        lightbox.setAttribute('aria-hidden', 'true');
        document.body.classList.remove('lightbox-open');
        lightboxImage.src = '';
        lightboxImage.alt = '';

        if (lastFocusedElement instanceof HTMLElement) {
            lastFocusedElement.focus();
        }
    }

    document.addEventListener('click', (event) => {
        const trigger = event.target.closest('.lightbox-trigger');

        if (trigger) {
            event.preventDefault();
            openLightbox(trigger);
            return;
        }

        if (event.target.closest('[data-lightbox-close]')) {
            closeLightbox();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeLightbox();
        }
    });

    lightboxImage.addEventListener('error', closeLightbox);
})();
