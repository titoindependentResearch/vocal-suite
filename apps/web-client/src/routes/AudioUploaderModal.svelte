<script>
  // Prop para comunicar el resultado al componente padre (+page.svelte)
  let { onProcessingComplete } = $props();

  let isModalOpen = $state(false);
  let selectedFile = $state(null);
  let isUploading = $state(false);
  let jobId = $state(null);
  let progress = $state(0);
  let stageMessage = $state("");
  let errorMessage = $state("");

  let pollInterval = null;

  function openModal() {
    isModalOpen = true;
    errorMessage = "";
  }

  function closeModal() {
    if (isUploading) return;
    isModalOpen = false;
    resetState();
  }

  function resetState() {
    selectedFile = null;
    isUploading = false;
    jobId = null;
    progress = 0;
    stageMessage = "";
    errorMessage = "";
    if (pollInterval) clearInterval(pollInterval);
  }

  function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
      selectedFile = file;
      errorMessage = "";
    }
  }

  async function startUploadProcess() {
    if (!selectedFile) return;

    isUploading = true;
    progress = 5;
    stageMessage = "Enviando archivo al servidor...";
    errorMessage = "";

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const res = await fetch("http://localhost:8005/api/audio/upload", {
        method: "POST",
        body: formData
      });

      if (!res.ok) {
        throw new Error("Error al subir el archivo de audio.");
      }

      const data = await res.json();
      jobId = data.job_id;

      // Iniciar consulta periódica (polling) del estado de la tarea
      pollInterval = setInterval(checkJobStatus, 1000);

    } catch (err) {
      errorMessage = err.message || "Ocurrió un error inesperado.";
      isUploading = false;
    }
  }

  async function checkJobStatus() {
    if (!jobId) return;

    try {
      const res = await fetch(`http://localhost:8005/api/audio/status/${jobId}`);
      if (!res.ok) throw new Error("No se pudo consultar el estado del procesamiento.");

      const data = await res.json();
      progress = data.progress;
      stageMessage = data.stage;

      if (data.status === "completed") {
        clearInterval(pollInterval);
        isUploading = false;
        
        // Notificar al componente padre con el resultado
        if (onProcessingComplete && data.result) {
          onProcessingComplete(data.result);
        }
        
        setTimeout(() => {
          closeModal();
        }, 1200);

      } else if (data.status === "failed") {
        clearInterval(pollInterval);
        isUploading = false;
        errorMessage = data.stage || "Falló el aislamiento vocal.";
      }
    } catch (err) {
      clearInterval(pollInterval);
      isUploading = false;
      errorMessage = err.message;
    }
  }
</script>

<!-- Botón para abrir el modal -->
<button
  onclick={openModal}
  class="w-full mb-3 py-2 px-4 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg transition-colors flex items-center justify-center gap-2 shadow-md"
>
  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
  </svg>
  Subir Nueva Canción (Procesar Audio Asíncrono)
</button>

<!-- Modal Overlay -->
{#if isModalOpen}
  <div class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
    <div class="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-5 shadow-2xl relative">
      
      <!-- Título -->
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-sm font-bold text-sky-400 uppercase tracking-wide">Separación de Pistas e Inferencia</h2>
        {#if !isUploading}
          <button onclick={closeModal} class="text-slate-400 hover:text-white font-bold text-lg">&times;</button>
        {/if}
      </div>

      {#if !isUploading && progress === 0}
        <!-- Formulario de Selección -->
        <div class="border-2 border-dashed border-slate-700 hover:border-sky-500/50 rounded-lg p-6 text-center transition-colors">
          <input
            type="file"
            accept="audio/*"
            onchange={handleFileSelect}
            class="hidden"
            id="audio-input"
          />
          <label for="audio-input" class="cursor-pointer flex flex-col items-center">
            <span class="text-2xl mb-2">🎵</span>
            <span class="text-xs font-medium text-slate-300">
              {selectedFile ? selectedFile.name : "Haz clic para seleccionar tu audio (.mp3, .wav)"}
            </span>
            <span class="text-[10px] text-slate-500 mt-1">Soporta formatos estándar de audio</span>
          </label>
        </div>

        {#if errorMessage}
          <p class="text-xs text-rose-400 mt-3 text-center">{errorMessage}</p>
        {/if}

        <div class="flex justify-end gap-2 mt-5">
          <button
            onclick={closeModal}
            class="px-3 py-1.5 text-xs rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Cancelar
          </button>
          <button
            onclick={startUploadProcess}
            disabled={!selectedFile}
            class="px-4 py-1.5 text-xs rounded font-semibold bg-sky-600 hover:bg-sky-500 text-white disabled:opacity-40 transition-colors"
          >
            Iniciar Procesamiento
          </button>
        </div>

      {:else}
        <!-- Barra de Progreso y Estado Asíncrono -->
        <div class="py-4">
          <div class="flex justify-between text-xs mb-2">
            <span class="text-slate-300 font-medium">{stageMessage}</span>
            <span class="text-sky-400 font-bold">{progress}%</span>
          </div>

          <!-- Barra -->
          <div class="w-full bg-slate-950 rounded-full h-3 overflow-hidden border border-slate-800">
            <div
              class="bg-gradient-to-r from-sky-500 to-emerald-400 h-full transition-all duration-300"
              style="width: {progress}%"
            ></div>
          </div>

          <p class="text-[11px] text-slate-500 text-center mt-4 animate-pulse">
            Aislando voz líder y calculando mapa microtonal...
          </p>
        </div>
      {/if}

    </div>
  </div>
{/if}