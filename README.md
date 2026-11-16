videos
## Recursos por mensaje privado («Comenta TUBO y te lo mando»)
Lo hace solo `dm_recursos.py` en cada vuelta de `publicar.yml`:
1. Busca en los reels de los últimos 7 días comentarios con una palabra clave de `recursos.json`. A cada persona, una sola vez: respuesta privada («sígueme y contéstame LISTO») y otra pública bajo su comentario («Mira tu DM»).
2. Si escribe LISTO y te sigue, le manda la imagen y las gracias (con la invitación a 🔁). Si no te sigue, un solo aviso; cuando vuelva a escribir LISTO siguiéndote, se la manda.
3. Todo queda en `dm.json`: nunca se escribe dos veces lo mismo a nadie.

Añadir un recurso nuevo (p. ej. GRUPO): copiar la imagen a `r/<nombre al azar>.jpg` y añadir en `recursos.json` la clave con `imagen`, `pedir` y `gracias`. Instagram solo deja mandar la imagen desde un enlace público, por eso vive en `r/` con un nombre que no se puede adivinar. Probar sin enviar nada: `PRUEBA=1 python3 dm_recursos.py` (con IG_TOKEN e IG_USER_ID).
