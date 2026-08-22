# ДССЗЗІ — український контент для CISO Assistant

Інструменти та бібліотеки для адаптації CISO Assistant під українську нормативну базу
(НД ТЗІ 3.6-006-24 та базові профілі безпеки ДССЗЗІ).

## Джерела

| Документ | Опис | Локальний шлях |
|---|---|---|
| НД ТЗІ 3.6-006-24 | «Порядок вибору заходів захисту інформації…» — каталог заходів захисту, український переклад NIST SP 800-53 rev5 (596 стор.) | `~/projects/legal/НД_ТЗІ_3.6-006-24.pdf` |
| Базовий профіль безпеки (ВК) | Профіль для систем з відкритою/конфіденційною інформацією | `~/projects/legal/профіль_вконф.pdf` |

Офіційне джерело: Адміністрація Держспецзв'язку (ДССЗЗІ). PDF у репозиторій не включені
(авторські права); для відтворення пайплайну потрібна локальна копія.

## Файли

- `nd-tzi-3-6-controls.yaml` — бібліотека каталогу заходів захисту (reference controls).
  Родини: AC (147), AT (17), AU (69), CA (32), CM (66), CP (56), IA (70). URN: `urn:intuitem:risk:library:dsszzi-nd-tzi-3-6-controls`.
- `dsszzi-base-security-profile.yaml` — фреймворк базового профілю безпеки
  (99 вимог, implementation groups VK/DSK, questions для параметрів).
- `parse_nd_tzi_family.py` — парсер родини заходів з текстового дампа PDF.
- `extract_parameters.py` — видобуток параметрів `[Вибір …]`/`[Призначення …]`;
  `--patch` додає блок «Параметри:» в описи контролів.
- `generate_questions.py` — генерує `questions` у вимогах фреймворку з параметрів
  каталогу (`--patch` пише у YAML).
- `build_content.py` — наповнення xlsx базового профілю з тексту профілю ВК.

## Пайплайн додавання родини

```bash
pdftotext ~/projects/legal/НД_ТЗІ_3.6-006-24.pdf /tmp/ndtzi_full.txt
python3 parse_nd_tzi_family.py /tmp/ndtzi_full.txt AU > au_parsed.yaml
# рев'ю тексту (Obsidian-нотатка) → правки → злиття в nd-tzi-3-6-controls.yaml:
#   category/csf_function, блоки «Параметри:», бамп version
# імпорт: stdin у manage.py shell → StoredLibrary.store_library_content + LoadedLibrary.update
```

Вилучені в оригіналі контролі (наприклад, AC-13, AT-5) зберігаються порожніми записами
для збереження нумерації. Назви — sentence case за схемою «База — Посилення».
