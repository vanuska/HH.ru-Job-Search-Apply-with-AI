import urllib.request
import json

def get_free_models():
    try:
        req = urllib.request.Request(
            'https://openrouter.ai/api/v1/models',
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        free_models = []
        for model in data.get('data', []):
            model_id = model.get('id', '')
            if ':free' in model_id or model_id == 'openrouter/free':
                free_models.append(model_id)
        
        return free_models
    except Exception as e:
        print(f"Ошибка: {e}")
        return []

if __name__ == "__main__":
    models = get_free_models()
    print("\n📋 Доступные бесплатные модели на OpenRouter:")
    print("="*60)
    for i, model in enumerate(sorted(models), 1):
        print(f"{i}. {model}")
    print("="*60)
    print(f"\nВсего: {len(models)} моделей")
