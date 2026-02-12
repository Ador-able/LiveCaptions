# 步骤 4: 术语提取 (LLM)
def step_terminology_extraction(task_id: str, db: Session):
    logger.info(f"任务 {task_id}: 开始术语提取...")

    task = crud.get_task(db, task_id)
    metadata = task.task_metadata or {}
    segments = metadata.get("compliant_segments", [])

    # 从任务配置中获取 LLM 设置
    llm_config = task.llm_config or {}
    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model = llm_config.get("model", "gpt-4o")

    # 将所有文本合并，用于术语提取
    full_text = "\n".join([s["text"] for s in segments])

    # 实例化 LLMService，传入任务特定的配置
    llm_service = LLMService(api_key=api_key, base_url=base_url, model=model)
    terminology_json = llm_service.extract_terminology(full_text, task.source_language, task.target_language)

    metadata["terminology"] = terminology_json

    crud.update_task(db, task_id, {
        "progress": 60.0,
        "current_step": "术语提取完成",
        "task_metadata": metadata
    })

# 步骤 5: 三步翻译 (LLM)
def step_translation(task_id: str, db: Session):
    logger.info(f"任务 {task_id}: 开始三步翻译流程...")

    task = crud.get_task(db, task_id)
    metadata = task.task_metadata or {}
    segments = metadata.get("compliant_segments", [])
    terminology = metadata.get("terminology", "[]")

    # 从任务配置中获取 LLM 设置
    llm_config = task.llm_config or {}
    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model = llm_config.get("model", "gpt-4o")

    # 实例化 LLMService，传入任务特定的配置
    llm_service = LLMService(api_key=api_key, base_url=base_url, model=model)

    translated_segments = []
    total_segments = len(segments)

    # 逐句或逐批翻译
    for i, segment in enumerate(segments):
        source_text = segment["text"]
        translated_text = llm_service.three_step_translation(
            source_text,
            task.source_language,
            task.target_language,
            terminology
        )

        new_segment = segment.copy()
        new_segment["text"] = translated_text
        new_segment["original_text"] = source_text
        translated_segments.append(new_segment)

        # 更新进度 (60% -> 90%)
        current_progress = 60.0 + (30.0 * (i + 1) / total_segments)
        if i % max(1, total_segments // 10) == 0:
            crud.update_task(db, task_id, {"progress": current_progress})

    metadata["translated_segments"] = translated_segments

    crud.update_task(db, task_id, {
        "progress": 90.0,
        "current_step": "翻译完成",
        "task_metadata": metadata
    })
