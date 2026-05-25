# Ex8 — Voice pipeline

## Your answer

The voice pipeline operates in two modes under a shared trace-event contract: text mode reads stdin and generates replies via Llama-3.3-70B, while voice mode uses Speechmatics for speech-to-text.

To ensure graceful degradation, voice mode immediately falls back to text mode if the required API key or library import is missing. This allows the system to pass CI checks without live credentials. Both modes emit identical trace events (voice.utterance_in and voice.utterance_out) containing the text, turn, and active mode, ensuring consistent downstream analysis. Finally, the ManagerPersona class manages conversation history and uses a fixed seed to keep LLM responses deterministic and tests stable.

## Citations

- starter/voice_pipeline/voice_loop.py — run_voice_mode
- starter/voice_pipeline/manager_persona.py — LLM-backed persona
