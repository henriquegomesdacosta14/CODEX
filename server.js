const express = require('express');
const app = express();
app.use(express.json({ limit: '10mb' }));
app.use(express.static('public'));

const GEMINI_KEY = process.env.GEMINI_KEY;

// Try-on endpoint
app.post('/api/tryon', async (req, res) => {
  try {
    const { personBase64, garmentBase64 } = req.body;
    const fetch = require('node-fetch');

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${GEMINI_KEY}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{
            parts: [
              { text: "You are a virtual try-on AI. Generate a realistic image showing the person wearing the garment from the second image. Keep the person's face, body shape, pose and background exactly the same. Only change the clothing to match the garment. Return only the result image as base64 JPEG." },
              { inline_data: { mime_type: "image/jpeg", data: personBase64 } },
              { inline_data: { mime_type: "image/jpeg", data: garmentBase64 } }
            ]
          }],
          generationConfig: { response_mime_type: "image/jpeg" }
        })
      }
    );

    const data = await response.json();
    const imageData = data?.candidates?.[0]?.content?.parts?.[0]?.inline_data?.data;
    if (!imageData) throw new Error(JSON.stringify(data));
    res.json({ success: true, image: imageData });
  } catch(e) {
    res.status(500).json({ success: false, error: e.message });
  }
});

// Suggest looks endpoint  
app.post('/api/suggest', async (req, res) => {
  try {
    const { clothes, occasion, time, weather, style } = req.body;
    const fetch = require('node-fetch');

    const clothesList = clothes.map(c => `- ${c.nome} (${c.cat})`).join('\n');

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_KEY}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{
            parts: [{ text: `Você é estilista brasileiro. Sugira 3 looks completos para:
Ocasião: ${occasion} | Horário: ${time} | Clima: ${weather} | Estilo: ${style}

Roupas disponíveis:
${clothesList}

Responda APENAS em JSON:
{"intro":"frase motivacional","looks":[{"nome":"nome","top":"nome exato do top","combinacao":["peça1","peça2","peça3"],"descricao":"por que funciona","dica":"dica rápida"}]}` }]
          }]
        })
      }
    );

    const data = await response.json();
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
    const clean = text.replace(/```json|```/g, '').trim();
    res.json({ success: true, result: JSON.parse(clean) });
  } catch(e) {
    res.status(500).json({ success: false, error: e.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Running on port ${PORT}`));
