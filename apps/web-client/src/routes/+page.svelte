<script>
  import { onMount, onDestroy } from 'svelte';
  import AudioUploaderModal from './AudioUploaderModal.svelte';

  // --- Estados reactivos Svelte 5 ($state) ---
  let isMicActive = $state(false);
  let isConnected = $state(false);
  let ws = $state(null);
  let audioRef = $state(null);
  let canvasRef = $state(null);
  let currentAudioTime = $state(0);
  let currentNote = $state("---");
  let currentFreqVal = $state(0.0);
  let currentCents = $state(0.0);
  let currentColor = $state("#00ff88");
  let wsStatus = $state("Desconectado");

  // --- Estado Transposición de Tono ---
  let currentSemitones = $state(0);
  let isShifting = $state(false);

  // --- Estado Congelado para Diagnóstico ---
  let lastDiagnosticCents = $state(0.0);
  let lastDiagnosticNote = $state("---");
  let lastDiagnosticColor = $state("#00ff88");
  let hasDiagnosticHistory = $state(false);

  // --- Variables de Audio Internas ---
  let mediaStream = null;
  let audioContext = null;
  let scriptNode = null;

  // --- Datos cargados del API Gateway ---
  let pitchMapData = $state(null);
  let livePitchHistory = $state([]);
  let animationFrameId;

  // Extraer el arreglo de sílabas/letras cargado desde el backend
  function getLyricsList() {
    if (pitchMapData) {
      if (Array.isArray(pitchMapData.lyrics_map) && pitchMapData.lyrics_map.length > 0) {
        return pitchMapData.lyrics_map;
      }
      if (Array.isArray(pitchMapData.syllables) && pitchMapData.syllables.length > 0) {
        return pitchMapData.syllables;
      }
      if (pitchMapData.pitch_map && Array.isArray(pitchMapData.pitch_map.lyrics_map) && pitchMapData.pitch_map.lyrics_map.length > 0) {
        return pitchMapData.pitch_map.lyrics_map;
      }
    }
    return [];
  }

  // Verso dinámico en tiempo real para la tarjeta de diagnóstico
  let currentSyllableText = $derived.by(() => {
    const lyrics = getLyricsList();
    if (lyrics.length === 0) return "Cargando letra de la canción...";

    const activeItem = lyrics.find(
      (item) => currentAudioTime >= (item.start ?? item.time) && currentAudioTime <= (item.end ?? ((item.start ?? item.time) + 0.8))
    );

    return activeItem ? activeItem.text : "---";
  });

  // --- Manejo del WebSocket y Micrófono ---
  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    ws = new WebSocket('ws://localhost:8005/api/ws/coach');

    ws.onopen = () => {
      isConnected = true;
      wsStatus = "Conectado";
    };

    ws.onmessage = (event) => {
      try {
        const messageData = JSON.parse(event.data);
        if (messageData.freq !== undefined && messageData.freq > 0) {
          currentFreqVal = messageData.freq;
          if (messageData.target || messageData.note) {
            currentNote = messageData.target || messageData.note;
          }
          if (messageData.cents !== undefined) {
            currentCents = messageData.cents;
          }
          if (messageData.color) {
            currentColor = messageData.color;
          }

          const isAudioPaused = audioRef && audioRef.paused;
          if (!isAudioPaused) {
            lastDiagnosticCents = currentCents;
            lastDiagnosticNote = currentNote;
            lastDiagnosticColor = currentColor;
            hasDiagnosticHistory = true;

            livePitchHistory = [
              ...livePitchHistory, 
              { 
                time: currentAudioTime, 
                freq: messageData.freq, 
                cents: messageData.cents || 0.0,
                color: messageData.color || '#00ff88'
              }
            ];

            if (livePitchHistory.length > 5000) {
              livePitchHistory.shift();
            }
          }
        }
      } catch (e) {
        console.error("Error procesando mensaje WS:", e);
      }
    };

    ws.onerror = () => { wsStatus = "Error de conexión"; };
    ws.onclose = () => { isConnected = false; wsStatus = "Desconectado"; };
  }

  async function startMicrophone() {
    try {
      connectWebSocket();
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      const source = audioContext.createMediaStreamSource(mediaStream);
      
      scriptNode = audioContext.createScriptProcessor(4096, 1, 1);
      scriptNode.onaudioprocess = (event) => {
        if (!isMicActive || !ws || ws.readyState !== WebSocket.OPEN) return;
        const inputBuffer = event.inputBuffer.getChannelData(0);
        const pcm16 = new Int16Array(inputBuffer.length);
        for (let i = 0; i < inputBuffer.length; i++) {
          pcm16[i] = Math.max(-1, Math.min(1, inputBuffer[i])) * 0x7FFF;
        }
        ws.send(pcm16.buffer);
      };

      source.connect(scriptNode);
      scriptNode.connect(audioContext.destination);
      isMicActive = true;
    } catch (err) {
      console.error("Error accediendo al micrófono:", err);
      isMicActive = false;
    }
  }

  function stopMicrophone() {
    isMicActive = false;
    if (scriptNode) { scriptNode.disconnect(); scriptNode = null; }
    if (mediaStream) { mediaStream.getTracks().forEach(track => track.stop()); mediaStream = null; }
    if (audioContext) { audioContext.close(); audioContext = null; }
    if (ws) { ws.close(); ws = null; }
    isConnected = false;
    wsStatus = "Desconectado";
  }

  function toggleMicrophone() {
    if (isMicActive) stopMicrophone();
    else startMicrophone();
  }

  onMount(async () => {
    try {
      const res = await fetch('http://localhost:8005/api/pitch-map');
      if (res.ok) {
        pitchMapData = await res.json();
      }
    } catch (e) {
      console.error("Error cargando pitch map:", e);
    }
    animLoop();
  });

  onDestroy(() => {
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    stopMicrophone();
  });

  function handleProcessedAudio(result) {
    pitchMapData = result;
    livePitchHistory = [];
    hasDiagnosticHistory = false;
    currentSemitones = 0;
    if (audioRef) {
      audioRef.src = result.vocal_audio_url;
      audioRef.load();
    }
  }

  async function requestPitchShift(step) {
    const targetSemitones = currentSemitones + step;
    if (targetSemitones < -6 || targetSemitones > 6) return;

    isShifting = true;
    try {
      const res = await fetch(`http://localhost:8005/api/audio/shift?semitones=${targetSemitones}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        currentSemitones = targetSemitones;
        pitchMapData = data.new_pitch_map;
        if (audioRef) {
          const currentTime = audioRef.currentTime;
          audioRef.src = data.new_audio_url;
          audioRef.load();
          audioRef.currentTime = currentTime;
        }
      }
    } catch (err) {
      console.error("Error ajustando tonalidad:", err);
    } finally {
      isShifting = false;
    }
  }

  function handleTimeUpdate() {
    if (audioRef) {
      currentAudioTime = audioRef.currentTime;
    }
  }

  function animLoop() {
    if (audioRef && !audioRef.paused) {
      currentAudioTime = audioRef.currentTime;
    }
    renderCanvas();
    animationFrameId = requestAnimationFrame(animLoop);
  }

  // Escala Frecuencia -> Coordenada Y
  function freqToY(freq, height) {
    if (!freq || freq <= 0) return -1;
    const minFreq = 60.0;
    const maxFreq = 800.0;
    const logMin = Math.log2(minFreq);
    const logMax = Math.log2(maxFreq);
    const logFreq = Math.log2(Math.max(minFreq, Math.min(maxFreq, freq)));
    return height - ((logFreq - logMin) / (logMax - logMin)) * height;
  }

  // BUCLE DE RENDERIZADO CANVAS (CURVAS + LÍRICA EN NEÓN)
  function renderCanvas() {
    if (!canvasRef) return;

    const width = canvasRef.clientWidth || 800;
    const height = canvasRef.clientHeight || 280;

    if (canvasRef.width !== width || canvasRef.height !== height) {
      canvasRef.width = width;
      canvasRef.height = height;
    }

    const ctx = canvasRef.getContext('2d');
    ctx.clearRect(0, 0, width, height);

    // Fondo Slate-950
    ctx.fillStyle = '#020617';
    ctx.fillRect(0, 0, width, height);

    // Líneas de cuadrícula
    ctx.strokeStyle = 'rgba(30, 41, 59, 0.4)';
    ctx.lineWidth = 1;
    for (let y = 40; y < height; y += 45) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    const windowSize = 5.0; // Ventana de 5 segundos
    const startTime = Math.max(0, currentAudioTime - 1.5);
    const endTime = startTime + windowSize;

    // 1. CURVA AZUL DE REFERENCIA
    const points = pitchMapData?.pitch_map || (Array.isArray(pitchMapData) ? pitchMapData : []);
    if (points.length > 0) {
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      let drawingRef = false;

      for (let point of points) {
        if (point && point.time >= startTime && point.time <= endTime) {
          const x = ((point.time - startTime) / windowSize) * width;
          const y = freqToY(point.freq, height);

          if (point.freq > 0 && y >= 0 && y <= height) {
            if (!drawingRef) { ctx.moveTo(x, y); drawingRef = true; }
            else { ctx.lineTo(x, y); }
          } else {
            drawingRef = false;
          }
        }
      }
      ctx.stroke();
    }

    // 2. CURVA TRAZO EN VIVO (VOZ DEL USUARIO)
    if (livePitchHistory.length > 0) {
      let drawingLive = false;
      for (let point of livePitchHistory) {
        if (point.time >= startTime && point.time <= endTime) {
          const x = ((point.time - startTime) / windowSize) * width;
          const y = freqToY(point.freq, height);

          if (point.freq > 0 && y >= 0 && y <= height) {
            ctx.fillStyle = point.color || '#00ff88';
            ctx.fillRect(x - 2, y - 2, 4, 4);

            if (!drawingLive) {
              ctx.beginPath();
              ctx.moveTo(x, y);
              drawingLive = true;
            } else {
              ctx.lineTo(x, y);
              ctx.strokeStyle = point.color || '#00ff88';
              ctx.lineWidth = 3;
              ctx.stroke();
              ctx.beginPath();
              ctx.moveTo(x, y);
            }
          } else {
            drawingLive = false;
          }
        }
      }
    }

    // 3. SÍLABAS Y PALABRAS EN NEÓN FLOTANDO SOBRE LA CURVA
    const lyricsList = getLyricsList();
    if (lyricsList.length > 0) {
      ctx.save();
      ctx.font = 'bold 14px sans-serif';
      ctx.textAlign = 'center';

      for (let lyric of lyricsList) {
        const lyricStart = lyric.start ?? lyric.time ?? 0;
        const lyricEnd = lyric.end ?? (lyricStart + 0.8);

        if (lyricStart >= startTime - 0.5 && lyricStart <= endTime) {
          const xPixel = ((lyricStart - startTime) / windowSize) * width;

          // Coordenada Y sobre la curva azul
          const matchingPoint = points.find(p => p && Math.abs(p.time - lyricStart) < 0.25);
          const freqVal = matchingPoint && matchingPoint.freq > 0 ? matchingPoint.freq : 220.0;
          const curveY = freqToY(freqVal, height);
          const yPixel = Math.max(38, curveY - 26);
          const textWidth = ctx.measureText(lyric.text).width;

          const isActive = currentAudioTime >= lyricStart && currentAudioTime <= lyricEnd;

          // Sombras y resplandor neón
          ctx.shadowBlur = 0;
          ctx.fillStyle = isActive ? 'rgba(0, 229, 255, 0.30)' : 'rgba(15, 23, 42, 0.90)';
          ctx.strokeStyle = isActive ? '#00E5FF' : '#38bdf8';
          ctx.lineWidth = isActive ? 2.0 : 1.2;

          ctx.beginPath();
          if (ctx.roundRect) {
            ctx.roundRect(xPixel - (textWidth / 2) - 8, yPixel - 15, textWidth + 16, 22, 6);
          } else {
            ctx.rect(xPixel - (textWidth / 2) - 8, yPixel - 15, textWidth + 16, 22);
          }
          ctx.fill();
          ctx.stroke();

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
  }
</script>

<main class="min-h-screen bg-slate-950 text-slate-100 p-4 flex flex-col items-center">
  <div class="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-2xl">
    
    <!-- Cabecera -->
    <div class="flex justify-between items-center mb-3">
      <div>
        <h1 class="text-lg font-bold text-sky-400">VocalSuite - Coaching de Afinación</h1>
        <p class="text-xs text-slate-400">Azul: Referencia (Salsa) | Trazo Dinámico: Tu Voz en Vivo</p>
      </div>
      <div class="flex items-center gap-2 text-xs bg-slate-950 px-3 py-1 rounded-full border border-slate-800">
        <span class="w-2 h-2 rounded-full {wsStatus === 'Conectado' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}"></span>
        <span class="text-slate-300">WebSocket: {wsStatus}</span>
      </div>
    </div>

    <!-- Módulo de Carga Asíncrona (Subida de Audio) -->
    <AudioUploaderModal onProcessingComplete={handleProcessedAudio} />

    <!-- Control de Transposición de Tono (Pitch Shift) -->
    <div class="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 mb-3 flex items-center justify-between">
      <div>
        <h3 class="text-sm font-bold text-slate-300">Tonalidad de la Pista</h3>
        <p class="text-[10px] text-slate-400">Ajusta el tono si la canción te queda muy aguda o grave</p>
      </div>
      
      <div class="flex items-center gap-3 bg-slate-900 border border-slate-700 rounded-lg p-1">
        <button 
          onclick={() => requestPitchShift(-1)}
          disabled={isShifting || currentSemitones <= -6}
          class="w-8 h-8 flex items-center justify-center bg-slate-800 hover:bg-slate-700 rounded text-slate-300 font-bold disabled:opacity-50 transition-colors"
        >
          -
        </button>
        
        <div class="w-16 text-center">
          <span class="text-sm font-bold text-sky-400">
            {currentSemitones > 0 ? '+' : ''}{currentSemitones}
          </span>
          <span class="text-[9px] block text-slate-400 uppercase">Semitonos</span>
        </div>

        <button 
          onclick={() => requestPitchShift(1)}
          disabled={isShifting || currentSemitones >= 6}
          class="w-8 h-8 flex items-center justify-center bg-slate-800 hover:bg-slate-700 rounded text-slate-300 font-bold disabled:opacity-50 transition-colors"
        >
          +
        </button>
      </div>
    </div>

    <!-- Panel Micrófono y Notas -->
    <div class="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 mb-3 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-2.5 h-2.5 rounded-full {isMicActive ? 'bg-emerald-500 animate-ping' : 'bg-slate-600'}"></span>
        <span class="text-sm font-medium">{isMicActive ? 'Micrófono Activo' : 'Micrófono Inactivo'}</span>
      </div>
      
      <div class="text-center">
        <p class="text-[10px] text-slate-400 uppercase tracking-wider">Nota / Desviación</p>
        <p class="text-xl font-bold" style="color: {currentColor}">{currentNote}</p>
        <p class="text-xs text-slate-400">({currentFreqVal.toFixed(1)} Hz | {currentCents > 0 ? '+' : ''}{currentCents.toFixed(1)} cents)</p>
      </div>

      <button 
        onclick={toggleMicrophone}
        class="px-4 py-2 text-sm rounded-lg font-medium transition-colors {isMicActive ? 'bg-rose-600 hover:bg-rose-700 text-white' : 'bg-emerald-600 hover:bg-emerald-700 text-white'}"
      >
        {isMicActive ? 'Apagar Micrófono' : 'Activar Micrófono'}
      </button>
    </div>

    <!-- TARJETA DE DIAGNÓSTICO -->
    <div class="mb-3 p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-start gap-3 shadow-md border-l-4" style="border-left-color: {hasDiagnosticHistory ? lastDiagnosticColor : '#00ff88'}">
      <div class="p-2 rounded-full bg-slate-900 border border-slate-800 text-xl flex-shrink-0">
        {#if hasDiagnosticHistory}
          {#if Math.abs(lastDiagnosticCents) <= 15}🎯{:else if lastDiagnosticCents > 15}📈{:else}📉{/if}
        {:else}
          🎙️
        {/if}
      </div>
      <div>
        <h3 class="text-xs font-bold text-slate-300 uppercase tracking-wide flex items-center gap-2">
          <span>Diagnóstico del Coach Vocal</span>
          {#if audioRef && audioRef.paused && hasDiagnosticHistory}
            <span class="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-normal border border-amber-500/30">PAUSA (RESULTADO CONSERVADO)</span>
          {/if}
        </h3>
        
        <div class="text-xs text-slate-200 mt-1">
          {#if !isMicActive}
            <span class="text-slate-400">Activa el micrófono para comenzar la evaluación en tiempo real.</span>
          {:else if !hasDiagnosticHistory}
            <span class="text-slate-400">Escuchando... Canta para obtener retroalimentación fisiológica.</span>
          {:else}
            <p class="text-sm font-bold text-cyan-400 mb-1">
              Verso: <span class="italic text-white">"{currentSyllableText}"</span>
            </p>
            <p>
              {#if Math.abs(lastDiagnosticCents) <= 15}
                <span class="text-emerald-400 font-semibold">¡Afinación excelente en {lastDiagnosticNote}!</span> Mantienes la colocación precisa y el apoyo de aire estable.
              {:else if lastDiagnosticCents > 15}
                <span class="text-amber-400 font-semibold">Tendencia Sostenida en {lastDiagnosticNote} (+{lastDiagnosticCents.toFixed(1)} cents):</span> Estás empujando con exceso de aire o tensión en la laringe. Relaja la garganta y apoya desde el diafragma.
              {:else}
                <span class="text-rose-400 font-semibold">Tendencia Bemolizada en {lastDiagnosticNote} ({lastDiagnosticCents.toFixed(1)} cents):</span> Falta de presión de aire o espacio resonante. Eleva el paladar blando y proyecta hacia la máscara.
              {/if}
            </p>
          {/if}
        </div>
      </div>
    </div>

    <!-- Reproductor de Audio -->
    <div class="mb-3">
      <audio 
        bind:this={audioRef}
        ontimeupdate={handleTimeUpdate}
        controls 
        src="http://localhost:8005/audio-files/vocals.wav" 
        class="w-full h-8"
      ></audio>
    </div>

    <!-- Lienzo Canvas Integrado -->
    <div class="relative w-full h-[280px] bg-slate-950 border border-slate-800 rounded-lg overflow-hidden shadow-inner">
      <canvas bind:this={canvasRef} class="w-full h-full block"></canvas>
    </div>

  </div>
</main>