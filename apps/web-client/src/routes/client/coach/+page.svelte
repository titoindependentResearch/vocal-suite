<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import PitchCanvas from '$lib/components/PitchCanvas.svelte';

    // Estados de conexión y audio
    let ws: WebSocket | null = null;
    let mediaStream: MediaStream | null = null;
    let audioContext: AudioContext | null = null;
    let processor: ScriptProcessorNode | null = null;
    let audioElement: HTMLAudioElement | null = $state(null);

    let connectionStatus = $state('Desconectado');
    let isSessionActive = $state(false);
    
    // Métricas en tiempo real recibidas por WebSocket
    let currentFreq = $state(0.0);
    let currentNote = $state('---');
    let currentCents = $state(0.0);
    let currentColor = $state('#64748b');
    let currentAudioTime = $state(0.0);

    // Datos del mapa de afinación y letras cargados de la API
    let pitchMapData = $state<any>(null);

    // ==============================================================================
    // OBTENER LA SÍLABA / VERSO ACTIVO REAL DE "NO ME MIRES MÁS"
    // ==============================================================================
    let currentSyllableText = $derived.by(() => {
        if (!pitchMapData) return "No me mires más";
        
        const lyrics = pitchMapData.lyrics_map || pitchMapData.syllables || [];
        if (!Array.isArray(lyrics) || lyrics.length === 0) return "No me mires más";

        // Buscar la sílaba activa según el segundo de reproducción actual
        const activeItem = lyrics.find(
            (item: any) => currentAudioTime >= item.start && currentAudioTime <= item.end
        );

        return activeItem ? activeItem.text : "No me mires más";
    });

    // Diagnóstico fisiológico vocal según desviación de cents
    let coachFeedback = $derived.by(() => {
        if (currentFreq <= 0) {
            return "Escuchando... Canta para obtener retroalimentación fisiológica.";
        }
        if (Math.abs(currentCents) <= 15) {
            return "¡Excelente afinación! Mantén el soporte diafragmático estable.";
        } else if (currentCents > 15) {
            return `Tendencia Sostenida en ${currentNote} (+${currentCents.toFixed(1)} cents): Estás empujando con exceso de aire o tensión en la laringe. Relaja la garganta.`;
        } else {
            return `Tendencia Bemolizada en ${currentNote} (${currentCents.toFixed(1)} cents): Falta de presión de aire o espacio resonante. Eleva el paladar blando.`;
        }
    });

    onMount(async () => {
        try {
            const res = await fetch('http://localhost:8005/api/pitch-map');
            if (res.ok) {
                pitchMapData = await res.json();
            }
        } catch (err) {
            console.error('Error al cargar pitch-map desde el API Gateway:', err);
        }
    });

    async function startCoachSession() {
        try {
            mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            audioContext = new AudioContext({ sampleRate: 16000 });
            
            const source = audioContext.createMediaStreamSource(mediaStream);
            processor = audioContext.createScriptProcessor(4096, 1, 1);

            ws = new WebSocket('ws://localhost:8005/api/ws/coach');

            ws.onopen = () => {
                connectionStatus = 'Conectado';
                isSessionActive = true;
            };

            processor.onaudioprocess = (e) => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    const inputData = e.inputBuffer.getChannelData(0);
                    const pcmData = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        pcmData[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
                    }
                    ws.send(pcmData.buffer);
                }
            };

            source.connect(processor);
            processor.connect(audioContext.destination);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                currentFreq = data.freq ?? 0.0;
                currentNote = data.note ?? '---';
                currentCents = data.cents ?? 0.0;
                currentColor = data.color ?? '#64748b';
            };

            ws.onclose = () => {
                stopCoachSession();
            };

        } catch (err) {
            console.error('Error al acceder al micrófono:', err);
            connectionStatus = 'Permiso denegado';
        }
    }

    function stopCoachSession() {
        if (processor && audioContext) {
            processor.disconnect();
            audioContext.close();
            processor = null;
            audioContext = null;
        }

        if (mediaStream) {
            mediaStream.getTracks().forEach(track => track.stop());
            mediaStream = null;
        }

        ws?.close();
        ws = null;
        isSessionActive = false;
        connectionStatus = 'Desconectado';
    }

    function handleTimeUpdate() {
        if (audioElement) {
            currentAudioTime = audioElement.currentTime;
        }
    }

    onDestroy(() => {
        stopCoachSession();
    });
</script>

<main class="flex flex-col items-center min-h-screen p-6 bg-slate-950 text-white font-sans">
    <div class="w-full max-w-4xl space-y-4">
        
        <!-- Encabezado con estado WebSocket -->
        <header class="flex justify-between items-center bg-slate-900 p-4 rounded-xl border border-slate-800">
            <div>
                <h1 class="text-xl font-bold text-sky-400">VocalSuite - Coaching de Afinación</h1>
                <p class="text-xs text-slate-400">Azul: Referencia (Salsa) | Trazo Dinámico: Tu Voz en Vivo</p>
            </div>
            <div class="flex items-center gap-2">
                <span class="w-3 h-3 rounded-full {isSessionActive ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}"></span>
                <span class="text-xs text-slate-300">WebSocket: {connectionStatus}</span>
            </div>
        </header>

        <!-- Control de Micrófono y Tonalidad -->
        <section class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex items-center justify-between">
                <div>
                    <p class="text-xs text-slate-400 uppercase font-semibold">Micrófono Activo</p>
                    <div class="text-xl font-black mt-1" style="color: {currentColor}">
                        {currentNote} <span class="text-sm font-normal">({currentFreq.toFixed(1)} Hz | {currentCents.toFixed(1)} cents)</span>
                    </div>
                </div>
                {#if !isSessionActive}
                    <button onclick={startCoachSession} class="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold text-sm transition-colors">
                        Encender Micrófono
                    </button>
                {:else}
                    <button onclick={stopCoachSession} class="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg font-bold text-sm transition-colors">
                        Apagar Micrófono
                    </button>
                {/if}
            </div>

            <!-- Banner con la sílaba/verso real de No Me Mires Más -->
            <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col justify-center">
                <p class="text-xs text-slate-400 uppercase font-semibold">DIAGNÓSTICO DEL COACH VOCAL</p>
                <p class="text-sm text-cyan-400 font-bold mt-1">
                    Verso: <span class="italic text-white">"{currentSyllableText}"</span>
                </p>
                <p class="text-xs text-slate-300 mt-1">{coachFeedback}</p>
            </div>
        </section>

        <!-- Reproductor de Pista de Referencia -->
        <div class="bg-slate-900 p-3 rounded-xl border border-slate-800">
            <audio 
                bind:this={audioElement} 
                src="http://localhost:8005/audio-files/vocals.wav" 
                controls 
                ontimeupdate={handleTimeUpdate}
                class="w-full"
            ></audio>
        </div>

        <!-- Lienzo Canvas Dual (Curva + Lírica Neón) -->
        <PitchCanvas 
            {currentAudioTime} 
            {pitchMapData} 
        />
    </div>
</main>