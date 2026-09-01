/*
 * Минимальный Vue 3 компонент (CDN, без сборки/npm) для панели HTML-тегов

 * Каждый .vue-comment-editor на странице (основная форма + активная форма
 * ответа, если она открыта) получает свой экземпляр приложения.
 */
(function () {
    if (typeof Vue === 'undefined') {
        return;
    }

    const CommentEditor = {
        data() {
            return {
                previewHtml: '',
                previewError: '',
                previewLoading: false,
            };
        },
        methods: {
            insertTag(tag) {
                const textarea = this.$refs.textInput;
                if (!textarea) {
                    return;
                }

                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                const selected = textarea.value.slice(start, end);

                let openTag = `<${tag}>`;
                const closeTag = `</${tag}>`;

                if (tag === 'a') {
                    const href = prompt('URL:', 'https://');
                    if (!href) {
                        return;
                    }
                    openTag = `<a href="${href}" title="">`;
                }

                textarea.setRangeText(openTag + selected + closeTag, start, end, 'end');
                textarea.focus();
            },

            runPreview() {
                const textarea = this.$refs.textInput;
                if (!textarea) {
                    return;
                }

                const form = textarea.closest('form');
                const csrfInput = form.querySelector('[name=csrfmiddlewaretoken]');
                const csrfToken = csrfInput ? csrfInput.value : '';

                this.previewLoading = true;
                this.previewError = '';

                fetch(window.COMMENT_PREVIEW_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken,
                    },
                    body: 'text=' + encodeURIComponent(textarea.value),
                })
                    .then((response) => response.json())
                    .then((data) => {
                        if (data.error) {
                            this.previewError = data.error;
                            this.previewHtml = '';
                        } else {
                            this.previewHtml = data.html;
                            this.previewError = '';
                        }
                    })
                    .catch(() => {
                        this.previewError = 'Не удалось получить предпросмотр.';
                        this.previewHtml = '';
                    })
                    .finally(() => {
                        this.previewLoading = false;
                    });
            },
        },
    };

    function mountEditors() {
        document.querySelectorAll('.vue-comment-editor').forEach((el) => {
            if (el.dataset.vueMounted) {
                return;
            }
            Vue.createApp(CommentEditor).mount(el);
            el.dataset.vueMounted = 'true';
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', mountEditors);
    } else {
        mountEditors();
    }

    // Форма ответа появляется в DOM динамически (при клике "Ответить" браузер
    // просто переходит по ссылке ?reply=<id>, страница перерисовывается на
    // сервере) — но на случай будущих live-вставок без перезагрузки страницы
    // держим mountEditors доступной глобально.
    window.mountCommentEditors = mountEditors;
})();
