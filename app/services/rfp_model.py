from app.services.rfp_model_runner import run_rfp_model


def call_local_rfp_model(text: str, model_name: str | None = None) -> dict:
    return run_rfp_model(text, model_name=model_name)
