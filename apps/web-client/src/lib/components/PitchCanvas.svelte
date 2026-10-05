<script>
  import { onMount, tick } from 'svelte';

  let { 
    currentAudioTime = 0, 
    pitchMapData = null 
  } = $props();

  let localPitchMap = $state(null);
  let canvasRef = $state(null);

  function getPoints(data) {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.pitch_map)) return data.pitch_map;
    if (data.pitch_map && Array.isArray(data.pitch_map.pitch_map)) return data.pitch_map.pitch_map;
    return [];
  }

  function getLyrics(data) {
    if (!data) return [];
    if (Array.isArray(data.lyrics_map)) return data.lyrics_map;
    if (Array.isArray(data.syllables)) return data.syllables; // Soporte para el formato syllables
    return [];
  }

  let activeData = $derived.by(() => {
    const propPoints = getPoints(pitchMapData);
    if (propPoints.length > 0) return pitchMapData;
    return localPitchMap;
  });

  function renderDualCurves(currentTimeToUse) {
    if (!canvasRef) return;
    
    try {
      const width = canvasRef.clientWidth || 800;
      const height = canvasRef.clientHeight || 350;

      if (canvasRef.width !== width || canvasRef.height !== height) {
        canvasRef.width = width;
        canvasRef.height = height;
      }

      const ctx = canvasRef.getContext('2d');
      ctx.clearRect(0, 0, width, height);

      // Fondo Slate-950
      ctx.fillStyle = '#020617';
      ctx.fillRect(0, 0, width, height);

      const points = getPoints(activeData);
      const lyricsData = getLyrics(activeData);

      // Guías de cuadrícula
      ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
      ctx.lineWidth = 1;
      for (let y = 50; y < height; y += 50) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }

      if (points.length === 0) {
        ctx.fillStyle = '#64748b';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⏳ Obteniendo mapa de afinación del servidor...', width / 2, height / 2);
        return;
      }

      const windowSize = 5.0; // Ventana de 5 segundos
      const startTime = Math.max(0, currentTimeToUse - 1.5);
      const endTime = startTime + windowSize;

      // Diagnóstico HUD en pantalla
      let activePointsCount = 0;
      let currentFreqDisplay = 0;

      for (let point of points) {
        if (point && point.time >= startTime && point.time <= endTime) {
          if (point.freq > 0) activePointsCount++;
          if (Math.abs(point.time - currentTimeToUse) < 0.15) {
            currentFreqDisplay = point.freq;
          }
        }
      }

      // Texto de estado HUD arriba a la izquierda
      ctx.fillStyle = '#64748b';
      ctx.font = '12px monospace';
      ctx.textAlign = 'left';
      ctx.fillText(
        `⏱️ ${currentTimeToUse.toFixed(1)}s | Puntos en ventana: ${activePointsCount} | Ref: ${currentFreqDisplay > 0 ? currentFreqDisplay.toFixed(1) + ' Hz' : 'Sin tono grabado (0 Hz)'}`,
        15, 
        22
      );

      // Dibujar Curva Azul de Referencia
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      let drawing = false;

      const minFreq = 60.0;   // Rango ampliado
      const maxFreq = 800.0; 
      const logMin = Math.log2(minFreq);
      const logMax = Math.log2(maxFreq);

      for (let point of points) {
        if (point && typeof point.time === 'number' && point.time >= startTime && point.time <= endTime) {
          const x = ((point.time - startTime) / windowSize) * width;
          const freqVal = typeof point.freq === 'number' ? point.freq : 0;
          const logFreq = freqVal > 0 ? Math.log2(Math.max(minFreq, Math.min(maxFreq, freqVal))) : logMin;
          const y = height - ((logFreq - logMin) / (logMax - logMin)) * height;
          
          if (freqVal > 0 && y >= 0 && y <= height) {
            if (!drawing) { 
              ctx.moveTo(x, y); 
              drawing = true; 
            } else { 
              ctx.lineTo(x, y); 
            }
          } else {
            drawing = false;
          }
        }
      }
      ctx.stroke();

      // ====================================================================
      // DIBUJAR LÍRICA DINÁMICA FLOTANDO SOBRE LA CURVA
      // ====================================================================
      if (lyricsData.length > 0) {
        ctx.save();
        ctx.font = 'bold 15px sans-serif';
        ctx.textAlign = 'center';

        for (let lyric of lyricsData) {
          const lyricStart = lyric.start ?? lyric.time ?? 0;
          const lyricEnd = lyric.end ?? (lyricStart + 0.8);

          if (lyricStart >= startTime - 0.5 && lyricStart <= endTime) {
            const xPixel = ((lyricStart - startTime) / windowSize) * width;

            // 1. Buscar la frecuencia de la nota en ese tiempo para situar 'Y' sobre el trazo
            const matchingPoint = points.find(p => p && Math.abs(p.time - lyricStart) < 0.25);
            const freqVal = matchingPoint && matchingPoint.freq > 0 ? matchingPoint.freq : (currentFreqDisplay > 0 ? currentFreqDisplay : 200.0);

            // 2. Calcular coordenada Y logarítmica
            const logFreq = Math.log2(Math.max(minFreq, Math.min(maxFreq, freqVal)));
            const curveY = height - ((logFreq - logMin) / (logMax - logMin)) * height;

            // Situar la caja 28px por encima de la curva de tono (con límite mínimo de 40px para el HUD)
            const yPixel = Math.max(42, curveY - 28);
            const textWidth = ctx.measureText(lyric.text).width;

            // 3. Evaluar si la sílaba/palabra se está cantando en este instante
            const isActive = currentTimeToUse >= lyricStart && currentTimeToUse <= lyricEnd;

            // Resetear sombras por iteración
            ctx.shadowBlur = 0;
            ctx.shadowColor = 'transparent';

            // Caja de fondo
            ctx.fillStyle = isActive ? 'rgba(0, 229, 255, 0.25)' : 'rgba(15, 23, 42, 0.90)';
            ctx.strokeStyle = isActive ? '#00E5FF' : '#38bdf8';
            ctx.lineWidth = isActive ? 2.0 : 1.2;
            
            ctx.beginPath();
            if (ctx.roundRect) {
              ctx.roundRect(xPixel - (textWidth / 2) - 8, yPixel - 16, textWidth + 16, 24, 6);
            } else {
              ctx.rect(xPixel - (textWidth / 2) - 8, yPixel - 16, textWidth + 16, 24);
            }
            ctx.fill();
            ctx.stroke();

            // Texto Resplandeciente Neón
            if (isActive) {
              ctx.shadowColor = '#00E5FF';
              ctx.shadowBlur = 12;
              ctx.fillStyle = '#00E5FF';
            } else {
              ctx.fillStyle = '#94a3b8';
            }

            ctx.fillText(lyric.text, xPixel, yPixel);
          }
        }
        ctx.restore();
      }

    } catch (err) {
      console.error("Error en renderizado Canvas:", err);
    }
  }

  onMount(async () => {
    await tick();

    if (getPoints(pitchMapData).length === 0) {
      try {
        let res = await fetch('http://localhost:8005/api/pitch-map');
        if (!res.ok) res = await fetch('/track_pitch.json');
        if (res.ok) {
          localPitchMap = await res.json();
        }
      } catch (err) {
        console.error("Error cargando mapa:", err);
      }
    }

    let animationFrameId;
    const updateLoop = () => {
      const audioElement = document.querySelector('audio');
      const timeToUse = audioElement ? audioElement.currentTime : (currentAudioTime || 0);
      
      renderDualCurves(timeToUse);
      animationFrameId = requestAnimationFrame(updateLoop);
    };

    animationFrameId = requestAnimationFrame(updateLoop);

    return () => {
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
    };
  });
</script>

<div class="flex justify-center w-full overflow-hidden rounded-xl border border-slate-700 shadow-xl">
  <canvas 
    bind:this={canvasRef}
    style="width: 100%; height: 350px; display: block; background-color: #020617; border-radius: 0.75rem;"
  ></canvas>
</div>