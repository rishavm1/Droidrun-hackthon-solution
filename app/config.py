from droidrun import DroidrunConfig

def get_agent_config() -> DroidrunConfig:
    config = DroidrunConfig()
    
    # Enable Reasoning (planning) and Vision (screen reading)
    config.agent.reasoning = True
    config.agent.manager.vision = True
    config.agent.executor.vision = True
    
    # Execution parameters
    config.agent.max_steps = 100
    config.agent.wait_for_stable_ui = 2.0
    
    return config