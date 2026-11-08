# FrameDiet 0.3: внешний корпус для `qa`

Прогон T1, 2026-11-09. Задача — проверить частоту `WARN`/`note:` и чувствительность `--freeze-warn-duration`; это не оценка качества видео или скиллов.

## Среда и корпус

- FrameDiet из checkout `ce510ce49aa28065b14d2e6ff90c013187744545`; порог по умолчанию не менялся.
- FFmpeg/ffprobe `9.0-full_build-www.gyan.dev`; Python `3.11.9`.
- Код из внешних репозиториев не запускался; пакеты и платные API не использовались.
- 10 MP4 из 6 репозиториев, фактически `70,117,445` байт (70.12 MB; 66.87 MiB). Все фактические размеры совпали с одобренным списком. SHA-256 и исходные URL записаны в [`qa-corpus-raw/sources.json`](qa-corpus-raw/sources.json).
- Сами ролики и превью лежат только в `C:\Temp\fd-corpus\framediet-0.3-2026-11-08`. В репозитории сохранены только источники, метаданные ffprobe и JSON-результаты FrameDiet; внешнее видео не включено.
- Тип ролика — грубая тематическая группировка по описанию/назначению примера. Корпус собран из опубликованных примеров и релизов; это отобранные демонстрации, а не случайная выборка обычных пользовательских рендеров.

## Источники

| Репозиторий | Ролики в корпусе | Материалы и лицензии |
|---|---:|---|
| `actionow-ai/vvv` | 5 | [starter](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/starter.mp4), [album-vertical](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/album-vertical.mp4), [cinema](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/cinema.mp4), [comedy](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/comedy.mp4), [doodle](https://raw.githubusercontent.com/actionow-ai/vvv/main/docs/assets/doodle.mp4); [MEDIA_LICENSE](https://github.com/actionow-ai/vvv/blob/main/MEDIA_LICENSE.md). |
| `Changroro/code-video` | 1 | [hero-45s.mp4](https://raw.githubusercontent.com/Changroro/code-video/main/docs/hero-45s.mp4); [репозиторий и README](https://github.com/Changroro/code-video). |
| `lemomo-ai/lemo-opuscar` | 1 | [archive-lighttable.mp4](https://github.com/lemomo-ai/lemo-opuscar/releases/download/web/archive-lighttable.mp4); [лицензия](https://github.com/lemomo-ai/lemo-opuscar#licence), [описание фильма](https://pdoom.video/styles/archive-lighttable/). |
| `mileson/chaojifeng-video-design` | 1 | [opuscar-swiss-motion sample](https://raw.githubusercontent.com/mileson/chaojifeng-video-design/main/styles/opuscar-swiss-motion/sample.mp4); [THIRD_PARTY_NOTICES](https://github.com/mileson/chaojifeng-video-design/blob/main/THIRD_PARTY_NOTICES.md). |
| `Aaryan-Kapoor/video-production-skill` | 1 | [product-walkthrough-demo.mp4](https://raw.githubusercontent.com/Aaryan-Kapoor/video-production-skill/main/examples/videos/product-walkthrough-demo.mp4); [репозиторий](https://github.com/Aaryan-Kapoor/video-production-skill). Отдельная лицензия именно на MP4 не найдена; файл включён в локальный прогон по одобренному списку и не перераспределяется. |
| `gnipbao/story-to-handdrawn-video` | 1 | [handdrawn-styles example](https://raw.githubusercontent.com/gnipbao/story-to-handdrawn-video/main/examples/style-showcase/handdrawn-styles-75-page-flip-45s-bgm.mp4); [BGM credits](https://github.com/gnipbao/story-to-handdrawn-video/blob/main/examples/style-showcase/BGM_CREDITS.md). У музыки указана CC BY 4.0 с атрибуцией; ролик не публикуется и не перераспределяется. |

## Команды и результаты

Точные команды и окружение — в [`qa-corpus-commands.txt`](qa-corpus-commands.txt). Сырые JSON `ffprobe` (10 файлов), QA (30 файлов) и текстовый вывод шести визуальных проверок лежат в [`qa-corpus-raw/`](qa-corpus-raw/). Таблица ниже воспроизводится командой `python -I bench\qa_corpus.py bench\qa-corpus-raw --output bench\qa-corpus-table.md`; скрипт читает только JSON и не открывает видео.

В столбцах `Notes` число — это количество элементов массива `notes`; одна строка note может перечислять несколько интервалов. Статусы даны в порядке 0,5 / 0,75 / 1,0 с.

## По роликам

| Файл | Тип | Длина | Видео / fps / звук | Статус 0,5 / 0,75 / 1,0 с | Notes 0,5 / 0,75 / 1,0 с | Warnings при 0,75 с (# + текст) | Notes при 0,75 с (# + текст) |
|---|---|---:|---|---|---|---|---|
| actionow-ai-vvv-starter.mp4 | motion graphics | 34.90 с | 1280x720 / 30 / 1 ауд. | PASS/PASS/PASS | 1/1/1 | 0: — | 1: black at start/end, likely a fade: 00:00:00.000 - 00:00:00.100 (0.10s), 00:00:34.567 - 00:00:34.867 (0.30s) |
| actionow-ai-vvv-album-vertical.mp4 | vertical motion graphics | 49.81 с | 540x960 / 30 / 1 ауд. | WARN/WARN/WARN | 1/1/1 | 1: audio peak -0.0 dBFS exceeds warning threshold -1.0 dBFS | 1: black at start/end, likely a fade: 00:00:49.433 - 00:00:49.767 (0.33s) |
| actionow-ai-vvv-cinema.mp4 | motion graphics | 115.84 с | 960x540 / 30 / 1 ауд. | WARN/WARN/WARN | 2/3/3 | 2: black intervals: 10 (00:00:11.233 - 00:00:11.700 (0.47s), 00:00:19.533 - 00:00:19.733 (0.20s), 00:00:27.833 - 00:00:32.367 (4.53s), 00:00:36.100 - 00:00:42.033 (5.93s), 00:00:52.667 - 00:00:58.567 (5.90s), +5 more); audio peak -1.0 dBFS exceeds warning threshold -1.0 dBFS | 3: black at start/end, likely a fade: 00:00:00.000 - 00:00:00.533 (0.53s), 00:01:54.767 - 00:01:55.800 (1.03s); still at start/end, likely a title or end card: 00:01:55.167 - 00:01:55.840 (0.67s); short stills under 0.75s, likely held beats: 00:00:39.467 - 00:00:39.967 (0.50s), 00:00:40.433 - 00:00:40.933 (0.50s) |
| actionow-ai-vvv-comedy.mp4 | motion graphics | 212.01 с | 960x540 / 30 / 1 ауд. | WARN/WARN/WARN | 1/2/2 | 1: freeze intervals: 3 (00:00:01.267 - 00:00:02.533 (1.27s), 00:01:24.633 - 00:01:25.467 (0.83s), 00:01:41.500 - 00:01:43.433 (1.93s)) | 2: black at start/end, likely a fade: 00:03:31.733 - 00:03:31.967 (0.23s); short stills under 0.75s, likely held beats: 00:00:02.767 - 00:00:03.300 (0.53s), 00:00:04.600 - 00:00:05.100 (0.50s) |
| actionow-ai-vvv-doodle.mp4 | illustrated animation | 142.02 с | 960x540 / 30 / 1 ауд. | WARN/WARN/WARN | 1/2/2 | 2: freeze intervals: 1 (00:02:06.733 - 00:02:08.400 (1.67s)); audio peak 0.3 dBFS exceeds warning threshold -1.0 dBFS | 2: still at start/end, likely a title or end card: 00:00:00.000 - 00:00:00.867 (0.87s); short stills under 0.75s, likely held beats: 00:00:14.200 - 00:00:14.733 (0.53s) |
| Changroro-code-video-hero-45s.mp4 | explainer/demo | 45.00 с | 1920x1080 / 30 / 1 ауд. | WARN/WARN/WARN | 1/2/2 | 2: freeze intervals: 5 (00:00:11.133 - 00:00:13.000 (1.87s), 00:00:13.300 - 00:00:14.800 (1.50s), 00:00:24.000 - 00:00:25.000 (1.00s), 00:00:31.967 - 00:00:33.000 (1.03s), 00:00:36.133 - 00:00:37.100 (0.97s)); audio peak 1.6 dBFS exceeds warning threshold -1.0 dBFS | 2: still at start/end, likely a title or end card: 00:00:43.500 - 00:00:44.667 (1.17s); short stills under 0.75s, likely held beats: 00:00:28.367 - 00:00:29.033 (0.67s), 00:00:30.500 - 00:00:31.000 (0.50s) |
| lemomo-ai-lemo-opuscar-archive-lighttable.mp4 | motion graphics | 40.00 с | 1280x720 / 24 / 1 ауд. | PASS/PASS/PASS | 1/1/1 | 0: — | 1: black at start/end, likely a fade: 00:00:00.083 - 00:00:00.208 (0.12s) |
| mileson-chaojifeng-opuscar-swiss-motion.mp4 | motion graphics | 44.00 с | 1280x720 / 24 / 1 ауд. | WARN/WARN/WARN | 1/2/2 | 2: freeze intervals: 4 (00:00:05.500 - 00:00:07.542 (2.04s), 00:00:10.000 - 00:00:11.542 (1.54s), 00:00:27.792 - 00:00:28.917 (1.12s), 00:00:30.000 - 00:00:31.792 (1.79s)); audio peak -0.7 dBFS exceeds warning threshold -1.0 dBFS | 2: still at start/end, likely a title or end card: 00:00:41.000 - 00:00:44.000 (3.00s); short stills under 0.75s, likely held beats: 00:00:04.500 - 00:00:05.167 (0.67s), 00:00:17.583 - 00:00:18.208 (0.62s), 00:00:20.958 - 00:00:21.542 (0.58s), 00:00:22.500 - 00:00:23.083 (0.58s) |
| Aaryan-Kapoor-product-walkthrough-demo.mp4 | product walkthrough | 10.00 с | 1280x720 / 12 / 0 ауд. | WARN/WARN/WARN | 1/1/1 | 1: freeze intervals: 1 (00:00:02.083 - 00:00:10.000 (7.92s)) | 1: still at start/end, likely a title or end card: 00:00:00.333 - 00:00:01.750 (1.42s) |
| gnipbao-handdrawn-styles-page-flip.mp4 | hand-drawn animation | 45.00 с | 1080x1440 / 30 / 1 ауд. | PASS/PASS/PASS | 1/1/1 | 0: — | 1: still at start/end, likely a title or end card: 00:00:00.000 - 00:00:01.033 (1.03s), 00:00:44.033 - 00:00:45.000 (0.97s) |

## По типам

| Тип | n | WARN 0,5 / 0,75 / 1,0 с | Доля WARN при 0,75 с | Среднее notes при 0,75 с |
|---|---:|---|---:|---:|
| explainer/demo | 1 | 1/1 / 1/1 / 1/1 | 100% | 2.00 |
| hand-drawn animation | 1 | 0/1 / 0/1 / 0/1 | 0% | 1.00 |
| illustrated animation | 1 | 1/1 / 1/1 / 1/1 | 100% | 2.00 |
| motion graphics | 5 | 3/5 / 3/5 / 3/5 | 60% | 1.80 |
| product walkthrough | 1 | 1/1 / 1/1 / 1/1 | 100% | 1.00 |
| vertical motion graphics | 1 | 1/1 / 1/1 / 1/1 | 100% | 1.00 |

## Сдвиги относительно порога 0,75 с

Отдельно считаются WARN-ролики и найденные freeze-интервалы: аудио/чёрные WARN могут сохранять статус ролика.

| Порог | WARN-ролики | Freeze WARN-интервалы, всего | Ролики: новые / исчезнувшие WARN относительно 0,75 с | Freeze-интервалы: появились / исчезли относительно 0,75 с |
|---:|---:|---:|---:|---:|
| 0,5 с | 7/10 | 25 | 0 / 0 | 11 / 0 |
| 0,75 с | 7/10 | 14 | — | — |
| 1,0 с | 7/10 | 12 | 0 / 0 | 0 / 2 |

## Визуальная проверка спорных сигналов

Выполнено по превью `qa --frames-dir` для шести роликов. Это проверка отдельных кадров по временам срабатывания, не просмотр полного видео. Выводы ниже — о вероятном намеренном приёме, а не о качестве скилла.

| Репозиторий / ролик | Сигнал и увиденное | Оценка и предложение правила |
|---|---|---|
| `actionow-ai/vvv`, cinema | 10 `black intervals`; в миниатюрах тёмных сцен видны части изображения, текст и световые детали. | Вероятный ложный сигнал для «чёрного кадра»: порог яркости зацепил тёмную цветокоррекцию. `blackdetect` следует считать подсказкой для просмотра; для тёмного материала проверять кадр и при необходимости отдельно настраивать `--black-pixel-threshold`. Сопутствующий аудио WARN остаётся числовым сравнением пика. |
| `actionow-ai/vvv`, comedy | Интервал `1.267–2.533 с` показывает статичную заставку/титры; в том же ролике есть ещё два freeze WARN, которые по этим превью однозначно не классифицируются. | Первый интервал похож на намеренную заставку, а не дефект. Для титров и кредитов правило должно разрешать статичный hold; остальные два сигнала остаются неразрешёнными без контекста полного ролика. |
| `actionow-ai/vvv`, doodle | Freeze `126.733–128.400 с`; кадр показывает иллюстрированную карточку “Thank you for coming”. | Вероятный ложный сигнал: статичная благодарственная карточка — ожидаемый приём. Граничная эвристика сейчас распознаёт только карточки у самого начала/конца; встроенные карточки в середине видео требуют просмотра контекста. |
| `Changroro/code-video`, hero | Пять freeze-интервалов совпадают с последовательностью объясняющих экранов/схем и шагов. | Похоже на намеренные остановки слайда, чтобы прочитать пояснение. Для обучающих схем freeze WARN должен оставаться сигналом к просмотру, а не автоматическим утверждением о дефекте. |
| `mileson/chaojifeng-video-design`, Swiss Motion | Четыре интервала показывают статичные типографические постеры и композиции, рассчитанные на чтение. | Вероятные намеренные holds. Для постерной motion graphics статичная композиция сама по себе не дефект; предупреждение требует проверки ожидаемого темпа/монтажа. |
| `Aaryan-Kapoor/video-production-skill`, product walkthrough | Freeze WARN `2.083–10.000 с`; миниатюры показывают последовательное добавление узлов на учебную схему, то есть изменения редкие и локальные. | Вероятный ложный сигнал «полной заморозки»: редкие обновления интерфейса могут выглядеть как freeze. Перед выводом о дефекте сравнивать начало, середину и конец интервала; здесь нужны более частые/контекстные кадры. |

Вероятные ложные сигналы перечислены с причиной и правилом проверки; они не используются как доказательство дефекта. На выборке остаются другие неразрешённые WARN: в частности, аудио-пик и ещё два freeze-интервала comedy. Пик в человекочитаемой строке округляется до 0.1 dBFS, поэтому значение вроде `-1.0 dBFS` может выглядеть равным порогу, хотя JSON содержит неокруглённое число немного выше него.

## Ограничения и вывод

- Маленькая выборка: 10 видео, 6 источников; пять видео пришли из одного репозитория. Категории, кроме motion graphics, представлены единичными примерами.
- Это опубликованные демонстрационные ролики, а не случайные пользовательские рендеры. Музыка, титры, карточки и авторские паузы меняют частоту срабатываний.
- Просмотрено не более шести роликов и только по кадрам `qa --frames-dir`; причины WARN по полному движению/монтажу не всегда устанавливаются по миниатюрам.
- `WARN` означает, что сработал измеримый сигнал (чёрные интервалы, low-motion, аудио-пик), а не что ролик или скилл плохой. `note:` также не подтверждает намерение автора.
- Менялись только пороги классификации freeze; прочие настройки `qa` оставались дефолтными. Код и порог по умолчанию не менялись. Набор тестов проекта не запускался.

**Вывод:** 0,75 с подходит как порог для сигнала к ручному просмотру, но не как автоматическое доказательство дефекта. На этой выборке 0,5 с добавляет 11 freeze-интервалов, а 1,0 с снимает 2 относительно 0,75 с; общий статус WARN остаётся у 7 из 10 при каждом пороге. Результаты не дают основания менять дефолт без большей размеченной выборки.
