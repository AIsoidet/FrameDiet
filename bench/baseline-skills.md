# Baseline: anatomy, watch, PixelFX и kinetic-film

## Метод

Табличные значения токенов взяты из `tiktoken` с `cl100k_base`. Это точные счётчики этой кодировки для каждого файла, но не токенизатор Claude. Ранее использовалась грубая оценка `bytes / 4`; она удалена, чтобы не смешивать методы. Разбивка разделов anatomy ниже показывает байтовый размер и долю от `SKILL.md`, а не токены.

Повторный запуск [`count_tokens.py`](count_tokens.py) использует `tiktoken`; первая загрузка кодировочных данных может потребовать сеть, если они ещё не закешированы. Для этого обновления использован уже установленный `tiktoken` и проверенный локальный кэш `cl100k_base`; ничего не устанавливалось и не скачивалось. Файлы-источники только читались, проектные скрипты и рендеры не запускались.

## anatomy

| Файл | Байты | Символы | `cl100k_base` tokens |
|---|---:|---:|---:|
| `SKILL.md` | 33 589 | 33 523 | 8 372 |
| `README.md` | 26 199 | 25 983 | 7 004 |
| `references/3d.md` | 44 644 | 44 345 | 12 543 |
| `references/craft.md` | 50 299 | 50 163 | 13 463 |
| `references/kit.md` | 67 873 | 67 723 | 19 151 |
| `references/motion.md` | 22 611 | 22 552 | 5 674 |
| `references/print.md` | 7 043 | 7 023 | 1 863 |
| `references/publish.md` | 4 113 | 4 113 | 1 010 |
| `references/react.md` | 3 614 | 3 606 | 894 |
| `references/verify.md` | 43 574 | 43 461 | 11 654 |
| `references/walkthrough.md` | 5 276 | 5 252 | 1 482 |
| `references/webgl.md` | 61 104 | 60 866 | 16 513 |
| **References total** | **310 151** | **309 104** | **84 247** |

### Scenario counts

Scenario totals below sum counts for each file independently; encoding all concatenated file contents as one prompt can differ slightly at file boundaries.

| Scenario | `cl100k_base` tokens |
|---|---:|
| `SKILL.md` only | 8 372 |
| `SKILL.md` + `references/craft.md` + `references/verify.md` | 33 489 |
| `SKILL.md` + all references | 92 619 |

### `SKILL.md` size by section

Section boundaries follow `##` headings; size is UTF-8 bytes. Percentages are of the full 33 589-byte file.

| Section | Bytes | Share |
|---|---:|---:|
| Preamble (frontmatter, H1, introduction) | 5 497 | 16% |
| The one idea that matters | 2 388 | 7% |
| Workflow | 6 894 | 21% |
| Setup | 5 272 | 16% |
| Craft rules (short form) | 4 951 | 15% |
| WebGL inside the drawing | 2 569 | 8% |
| 3D: figures that turn (beta) | 2 597 | 8% |
| Printable sheets (A4) | 1 493 | 4% |
| References | 1 928 | 6% |

### Notes

1. The main skill and reference files total 92 619 `cl100k_base` tokens when loaded together. The references alone account for 84 247.
2. The five largest references (`kit`, `webgl`, `craft`, `3d`, `verify`) total 73 324 tokens, about 87% of all references.
3. Workflow is the largest `SKILL.md` section by file size (6 894 bytes, 21%); the preamble is next (5 497 bytes, 16%). Exact per-section token counts were not preserved.
4. The `watch/SKILL.md` file contains 3 918 `cl100k_base` tokens. Its README is not included in this count.
5. This is a source-size snapshot. It does not measure which references a model actually loaded in a task or any end-to-end conversation savings.

## watch

| File | `cl100k_base` tokens |
|---|---:|
| `SKILL.md` | 3 918 |

## kinetic-test skill

| File | `cl100k_base` tokens |
|---|---:|
| `skill/SKILL.md` | 4 141 |
| `skill/references/blocks.md` | 3 062 |
| `skill/references/sound.md` | 1 569 |
| `skill/references/method.md` | 1 094 |
| `skill/references/render.md` | 1 051 |
| `skill/references/craft.md` | 915 |
| `skill/references/scenario-mcp.md` | 843 |
| **References total** | **8 534** |
| **SKILL + all references (sum of per-file counts)** | **12 675** |

The `kinetic-test` folder has no README alongside this skill. Counts are for the skill and its references only.

## PixelFX and kinetic-film inventory

- **PixelFX:** no skill instruction file was found in the local materials. PixelFX demo source, posts, and rendered media exist under the separate `AI_Channel` project, but this report contains no PixelFX token or video measurements.
- **Kinetic-film:** a separate local project under `kinetic-test` contains `skill/SKILL.md`, `scripts/finish.py`, references, and rendered clips. The skill and references are counted above; no media QA verdict or comparison with FrameDiet was produced.

These project names describe local inventory only. `baseline-tiktoken.txt` records the token counts used above; neither file is a before/after FrameDiet benchmark.
