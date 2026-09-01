-- Схема таблицы comments_comment (модель comments.Comment).
--
-- Реальная СУБД проекта — PostgreSQL (см. config/settings.py, DATABASES).
-- DDL ниже намеренно записан в MySQL-диалекте — специально для того, чтобы
-- его можно было импортировать в MySQL Workbench:
--   File -> Import -> Reverse Engineer SQL Script... -> db/schema.sql
-- и сразу получить ER-диаграмму для сверки с тем, что реально реализовано.
--
-- Соответствие типов Django-полей (comments/models.py) типам ниже:
--   user_name       CharField(max_length=100)              -> VARCHAR(100)
--   email           EmailField()  (max_length по умолчанию) -> VARCHAR(254)
--   home_page       URLField(blank=True)                    -> VARCHAR(200) NULL
--   text            TextField(validators=[MaxLength(5000)]) -> TEXT
--   attachment      FileField(blank=True)                   -> VARCHAR(100) NULL
--   attachment_kind CharField(max_length=5, choices=...)     -> VARCHAR(5) NULL
--   parent          ForeignKey('self', on_delete=CASCADE)    -> parent_id BIGINT NULL
--   created_at      DateTimeField(auto_now_add=True)         -> DATETIME(6)

CREATE TABLE comments_comment (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_name       VARCHAR(100)    NOT NULL,
    email           VARCHAR(254)    NOT NULL,
    home_page       VARCHAR(200)    NULL,
    text            TEXT            NOT NULL,
    attachment      VARCHAR(100)    NULL,
    attachment_kind VARCHAR(5)      NULL,
    parent_id       BIGINT UNSIGNED NULL,
    created_at      DATETIME(6)     NOT NULL,

    PRIMARY KEY (id),
    KEY idx_comments_comment_parent_id (parent_id),
    KEY idx_comments_comment_created_at (created_at),
    CONSTRAINT fk_comments_comment_parent
        FOREIGN KEY (parent_id) REFERENCES comments_comment (id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;