<script>
  let { pitchMapData, currentAudioTime, livePitchHistory } = $props();
  let canvasRef = $state(null);

  function renderDualCurves() {
    if (!canvasRef) return;
    const ctx = canvasRef.getContext('2d');
    ctx.clearRect(0, 0, canvasRef.width, canvasRef.height);

    const width = canvasRef.width;
    const height = canvasRef.height;
    const windowSize = 5.0; // Ventana de 5 segundos en pantalla
    const startTime = Math.max(0, currentAudioTime - 1.5);
    const endTime = startTime + windowSize;

    function getCoordinates(t, freq) {
      const x = ((t - startTime) / windowSize) * width;
      const minFreq = 65.0;  // C2
      const maxFreq = 1046.0; // C6
      const logMin = Math.log2(minFreq);
      const logMax = Math.log2(maxFreq);
      const logFreq = freq > 0 ? Math.log2(Math.max(minFreq, Math.min(maxFreq, freq))) : logMin;
      const y = height - ((logFreq - logMin) / (logMax - logMin)) * height;
      return { x, y: freq > 0 ? y : -100 };
    }

    // 1. Dibujar la Curva de Referencia (Cantante Original) - Azul Translúcido
    if (pitchMapData?.pitch_map) {
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.6)';
      ctx.lineWidth = 3;
      ctx.beginPath();
      let drawing = false;

      for (let point of pitchMapData.pitch_map) {
        if (point.time >= startTime && point.time <= endTime) {
          const { x, y } = getCoordinates(point.time, point.freq);
          if (point.freq > 0 && y > 0) {
            if (!drawing) { ctx.moveTo(x, y); drawing = true; } 
            else { ctx.lineTo(x, y); }
          } else {
            drawing = false;
          }
        }
      }
      ctx.stroke();
    }

    // 2. Dibujar la Curva del Alumno (Live WebSocket) - Verde Brillante
    if (livePitchHistory?.length > 0) {
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 4;
      ctx.beginPath();
      let liveDrawing = false;

      for (let p of livePitchHistory) {
        if (p.time >= startTime && p.time <= endTime) {
          const { x, y } = getCoordinates(p.time, p.freq);
          if (p.freq > 0 && y > 0) {
            if (!liveDrawing) { ctx.moveTo(x, y); liveDrawing = true; } 
            else { ctx.lineTo(x, y); }
          } else {
            liveDrawing = false;
          }
        }
      }
      ctx.stroke();
    }
  }

  // Ejecutar el renderizado en cada frame o cambio de tiempo
  $effect(() => {
    if (currentAudioTime || livePitchHistory) {
      requestAnimationFrame(renderDualCurves);
    }
  });
</script>

<canvas bind:this={canvasRef} width="800" height="300" class="bg-slate-900 rounded-lg shadow-inner"></canvas>
