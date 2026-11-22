# Reading Worksheet Studio

A teacher-facing prototype for INFH5000 Group 5, *Personalizing Reading Materials for Children with Dyslexia*. Choose one of the 15 English passages from the course appendix, review observations from a fictional assessment, and generate a learner worksheet and a teacher copy with answers and source quotations.

**Start with [the Markdown demo](Worksheet_Demo.md).** It opens directly on GitHub. Two children work toward the same comprehension goal using *The Red Ball*. One reads the original story in two-sentence blocks. The other practices connecting “he” to Tim. The assessments and worked examples were written for this demonstration. They are separate from live model output.

## Run on your Mac

Use Python 3.11 or 3.12. Open a terminal in the folder containing this README and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

Open the local URL printed in the terminal. **Worked examples** is ready immediately after installation. Select **Show teacher notes and answer key** to inspect the supporting evidence. The learner and teacher copies can each be downloaded as Markdown. Press Ctrl+C in the terminal to stop the app.

To reproduce the written demo with Python alone:

```bash
python3 demo.py > Worksheet_Demo.md
```

## Generate a worksheet

1. Open **Create worksheet** and select the provider. For **OpenAI**, enter your own API key in the password field or set `OPENAI_API_KEY` in the process environment. The suggested model is `gpt-4.1-mini`; enter another available chat model with JSON output if needed. The excerpt is sent to OpenAI when you click **Extract profile**. Generation sends the reviewed profile, including its supporting quotes, along with the passage, objective and activity instructions.
2. For **Ollama**, start the Ollama desktop application on the machine running Streamlit. Download a local model with `ollama pull gemma3:4b`, select **Ollama** in the app, and enter that same model name. Choose a model that fits your machine. The app connects to `127.0.0.1:11434`. The default model names can be overridden with `OPENAI_MODEL` or `OLLAMA_MODEL`.
3. Select a passage and write a lesson objective. Choose a fictional sample assessment or enter your own fictional excerpt. Select **Extract profile**. Check the findings against the displayed quotes and edit the proposed support. If there is no documented reading observation, the app returns an empty profile for review. Worksheet generation requires at least one supported finding.
4. Choose a teaching activity. The options are to apply the approved support, divide the original wording into shorter blocks, practice identifying whom or what a word refers to, or locate supporting words in the text. Pick a template that fits both the profile and the passage.
5. Confirm the profile and objective, then select **Generate worksheet**. Review the adapted passage, activity, questions and teacher key. Download the learner copy for the activity and the teacher copy for review.

Provider documentation: [OpenAI chat](https://developers.openai.com/api/reference/resources/chat), [local Ollama chat](https://docs.ollama.com/api/chat).

## How the workflow works

| Step | What the project does | What the teacher checks |
| --- | --- | --- |
| Extract observations | A model proposes findings and a support. Python checks that each quoted excerpt appears verbatim in the assessment before generation. | Whether the words actually support the interpretation. |
| Draft a worksheet | The same model receives the selected passage, corpus metadata, approved profile, lesson objective and chosen activity. | Whether the support is appropriate and the reading task still targets the objective. |
| Validate and export | Python checks for reading blocks, practice directions, questions, answers, a teacher note and verbatim source evidence for each answer. The shorter-block template also checks that the original wording, punctuation and order are preserved. A malformed or invalid draft gets one repair attempt. | Whether each answer follows from its quotation, the child can answer from the adapted text, and the passage preserves the source meaning. |

The source files are UTF-8 plain text. The corpus has five narratives (`N1–N5`), five informational texts (`I1–I5`) and five narratives with dialogue (`D1–D5`). Each genre contains one text per difficulty tier. Browse the [passages](data/passages/) or their [appendix metadata](data/corpus.json).

## Compare prompting approaches

`python3 compare.py` previews the experiment without making a request. To produce a fresh comparison, start a local Ollama model and run:

```bash
python3 compare.py --run --backend Ollama --model gemma3:4b > comparison.md
```

For hosted generation, set `OPENAI_API_KEY` and supply `--backend OpenAI --model gpt-4.1-mini`. The script generates one general worksheet (A), two conditioned on the raw excerpts (B), and two conditioned on the curated profiles (C). The general worksheet is shared by both comparisons. The passage, objective, model, output schema and repair allowance are held fixed. The result includes worksheets, completion status and an empty reviewer scoring table. Condition C starts with the hand-authored profile, so the comparison addresses worksheet generation after profile review. Both cases use one passage. Student learning outcomes would require a separate study.

## Project files

| Path | Purpose |
| --- | --- |
| `app.py` | Streamlit controls for selecting, reviewing, generating and downloading |
| `workflow.py` | Prompts, checks, revision and Markdown rendering |
| `providers.py` | OpenAI and local Ollama clients |
| `data/corpus.json`, `data/passages/*.txt` | The appendix metadata and 15 original reading paragraphs |
| `data/activities.json` | The four teaching activity templates |
| `examples/cases.json` | Two fictional excerpts, profiles and worked worksheets |
| `demo.py`, `Worksheet_Demo.md` | Reproducible offline demonstration |
| `compare.py` | Paired generation experiment for the two example profiles |
| `test_workflow.py` | Offline regression checks for corpus, examples, validation and exports |

For GitHub, put the contents of this folder at the root of your repository. A reader can open the Markdown demo there or clone the repository and run the app. Keep credentials in your environment and publish only fictional assessments. To check the project before submission, run `python3 -m unittest -v` from this folder.
