def write_with_openai(*args, **kwargs):
    raise RuntimeError("OpenAI provider não configurado neste patch local.")


def plan_visual_scenes_with_openai(*args, **kwargs):
    raise RuntimeError("OpenAI scene planner não configurado neste patch local.")
