<div align="center">
  <img src="./assets/stuff/light_logo.png" alt="Guardian of Light Logo" width="260"/>
</div>

# 🕯 Guardian of Light

Guardian of Light is an ambient, time-aware sentinel that watches the shifting light and responds with quiet, gothic-solarpunk commentary. More concretely, it is an Arduino-based light-sensitive display that reacts to changes in brightness and interprets them as states:

🌤 Day  
☀️ Bright  
🌆 Dusk  
🌙 Night  

Over time, it gained a "voice" through text generation and eventually a "body" through a 3D animated presence on the web. 

---

## Features

📟 Arduino light sensing and LCD output  
🧠 LLM-generated text  
🧍 Animated 3D character in Three.js  
📜 Typewriter-style scroll UI  
🕰 Time-aware state switching  

---

🧩 Architecture

This project is split into three conceptual layers:

1. The Senses
Arduino reads light values from an LDR and detects state changes.

2. The Mind
A Python script listens for state changes and asks a language model to produce a short, stylized response.

3. The Body
A Three.js frontend renders a living guardian whose appearance and animation shift with time and state. Character T-Poses were generated with GPT5.2, then uploaded to Tencent Hunyuan3D for 3D model generation and animation. 

---

## Why

This is an experiment in ambient interfaces, poetic machines, and slow software.

---

## License

MIT. Build your own guardians.
