import { useEffect, useRef, useState } from 'react';

type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type Message = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  message_type?: string;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

type DatasetSummary = {
  rows?: number;
  cols?: number;
  task_type?: string;
  target?: string;
  duplicates?: number;
  missing_cols?: number;
};

type ModelSummary = {
  best_model?: string;
  task_type?: string;
  metrics?: Record<string, number | string>;
};

type ChartSummary = {
  type: string;
  src: string;
  caption: string;
};

type Project = { id: string; name: string; createdAt: string };
type Task = { id: string; title: string; project: string; status: 'Todo' | 'Done' };
type Schedule = { id: string; name: string; date: string; frequency: string };
type GeneratedImage = { id: string; prompt: string; url: string; createdAt: string; status?: 'loading' | 'ready' | 'error' };

const quickPrompts = [
  'Create an image or sticker',
  'Write or edit',
  'Search the web',
];

const sidebarItems = [
  'Home',
  'Explore',
  'Images',
  'Library',
  'Tasks',
  'Scheduled',
  'Projects',
];

const recents = [
  'Customer churn analysis',
  'New dataset analysis',
  'Stroke prediction model',
  'Sales performance report',
  'Marketing campaign ideas',
];

const SESSION_KEY = 'autonomous_data_scientist_session';
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

const apiPath = (path: string) => (API_BASE ? `${API_BASE}${path}` : path);
const imageSeed = () => Date.now() % 2147483647;

export default function App() {
  const [sessionId, setSessionId] = useState<string>(() => localStorage.getItem(SESSION_KEY) || crypto.randomUUID());
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [search, setSearch] = useState('');
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [datasetSummary, setDatasetSummary] = useState<DatasetSummary | null>(null);
  const [modelSummary, setModelSummary] = useState<ModelSummary | null>(null);
  const [chartFrames, setChartFrames] = useState<ChartSummary[]>([]);
  const [statusText, setStatusText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadInfo, setUploadInfo] = useState<{ name: string; rows: number; cols: number; target?: string } | null>(null);
  const [activeSidebarView, setActiveSidebarView] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [projectName, setProjectName] = useState('');
  const [taskTitle, setTaskTitle] = useState('');
  const [taskProject, setTaskProject] = useState('');
  const [scheduleName, setScheduleName] = useState('');
  const [scheduleDate, setScheduleDate] = useState('');
  const [scheduleFrequency, setScheduleFrequency] = useState('Once');
  const [generatedImages, setGeneratedImages] = useState<GeneratedImage[]>([]);
  const [imagePrompt, setImagePrompt] = useState('');
  const [generatingImage, setGeneratingImage] = useState(false);
  const [activeMode, setActiveMode] = useState<'Chat' | 'Work'>('Chat');
  const capabilityScroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const storedProjects = localStorage.getItem('evolve_projects');
    const storedTasks = localStorage.getItem('evolve_tasks');
    const storedSchedules = localStorage.getItem('evolve_schedules');
    const storedImages = localStorage.getItem('evolve_images');
    if (storedProjects) setProjects(JSON.parse(storedProjects));
    if (storedTasks) setTasks(JSON.parse(storedTasks));
    if (storedSchedules) setSchedules(JSON.parse(storedSchedules));
    if (storedImages) {
      setGeneratedImages(JSON.parse(storedImages).map((image: GeneratedImage) => ({
        ...image,
        url: image.url.includes('image.pollinations.ai')
          ? apiPath(`/api/images/generate?prompt=${encodeURIComponent(image.prompt)}&seed=${Date.parse(image.createdAt) % 2147483647 || imageSeed()}`)
          : image.url,
        status: 'loading',
      })));
    }
  }, []);

  useEffect(() => { localStorage.setItem('evolve_projects', JSON.stringify(projects)); }, [projects]);
  useEffect(() => { localStorage.setItem('evolve_tasks', JSON.stringify(tasks)); }, [tasks]);
  useEffect(() => { localStorage.setItem('evolve_schedules', JSON.stringify(schedules)); }, [schedules]);
  useEffect(() => { localStorage.setItem('evolve_images', JSON.stringify(generatedImages)); }, [generatedImages]);

  useEffect(() => {
    localStorage.setItem(SESSION_KEY, sessionId);
    loadConversations();
  }, [sessionId]);

  useEffect(() => {
    if (!activeConversationId) return;
    loadConversation(activeConversationId);
  }, [activeConversationId]);

  const loadConversations = async () => {
    try {
      const response = await fetch(`${apiPath('/api/conversations')}?session_id=${sessionId}`);
      if (!response.ok) return;
      const data = await response.json();
      setConversations(Array.isArray(data) ? data : []);
      if (!activeConversationId && data.length > 0) {
        setActiveConversationId(data[0].id);
      }
    } catch (error) {
      console.warn('Could not fetch conversations', error);
    }
  };

  const loadConversation = async (conversationId: string) => {
    try {
      const response = await fetch(`${apiPath('/api/conversations')}/${conversationId}`);
      if (!response.ok) return;
      const data = await response.json();
      setMessages(data.messages || []);
      setDatasetSummary(null);
      setModelSummary(null);
      setChartFrames([]);
      if (data.messages?.length) {
        const datasetMessage = data.messages.find(
          (msg: Message) => msg.message_type === 'analysis' && msg.metadata && 'rows' in (msg.metadata || {}),
        );
        if (datasetMessage?.metadata) {
          const meta = datasetMessage.metadata as Record<string, unknown>;
          setDatasetSummary({
            rows: Number(meta.rows ?? meta.n_rows ?? 0),
            cols: Number(meta.cols ?? meta.n_cols ?? 0),
            task_type: String(meta.task_type ?? ''),
            target: String(meta.target ?? ''),
            duplicates: Number(meta.duplicates ?? 0),
            missing_cols: Number(meta.missing_cols ?? 0),
          });
        }
      }
      setStatusText('Conversation loaded');
    } catch (error) {
      console.warn('Could not load conversation', error);
    }
  };

  const createConversation = async (title = 'New analysis') => {
    const response = await fetch(`${apiPath('/api/conversations')}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, title }),
    });
    if (!response.ok) return null;
    const conversation = await response.json();
    setActiveConversationId(conversation.id);
    setMessages([]);
    await loadConversations();
    return conversation.id;
  };

  const deleteConversation = async (conversationId: string) => {
    const confirmed = window.confirm('Delete this conversation?');
    if (!confirmed) return;
    await fetch(`${apiPath('/api/conversations')}/${conversationId}`, { method: 'DELETE' });
    setConversations((current) => current.filter((item) => item.id !== conversationId));
    if (activeConversationId === conversationId) {
      setActiveConversationId(null);
      setMessages([]);
      setDatasetSummary(null);
      setModelSummary(null);
      setChartFrames([]);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    let conversationId = activeConversationId;
    if (!conversationId) {
      conversationId = await createConversation(file.name.slice(0, 60));
    }
    if (!conversationId) return;

    setUploading(true);
    setStatusText(`Uploading ${file.name}...`);

    const form = new FormData();
    form.append('file', file);
    form.append('conversation_id', conversationId);
    form.append('session_id', sessionId);

    try {
      const response = await fetch(`${apiPath('/api/upload')}`, { method: 'POST', body: form });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.detail || 'Upload failed');
      }
      setUploadInfo({
        name: result.filename,
        rows: result.media_type ? 0 : Number(result.n_rows),
        cols: result.media_type ? 0 : Number(result.n_cols),
        target: result.detected_target,
      });
      if (result.media_type) {
        setStatusText(`Uploaded ${result.filename}. Video processing is ready for the media workflow.`);
        await loadConversations();
        return;
      }
      setDatasetSummary({
        rows: Number(result.n_rows),
        cols: Number(result.n_cols),
        target: result.detected_target,
      });
      setStatusText(`Loaded ${result.filename} with ${result.n_rows} rows`);
      await loadConversations();
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isStreaming) return;

    let conversationId = activeConversationId;
    if (!conversationId) {
      conversationId = await createConversation(text.slice(0, 60));
    }
    if (!conversationId) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      message_type: 'text',
    };

    setMessages((current) => [
      ...current,
      userMessage,
      { id: crypto.randomUUID(), role: 'assistant', content: '', message_type: 'analysis' },
    ]);
    setInput('');
    setIsStreaming(true);
    setStatusText('Running analysis...');

    try {
      const response = await fetch(`${apiPath('/api/chat')}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          message: text,
          dataset_id: uploadInfo ? conversationId : undefined,
          target_col: datasetSummary?.target,
          business_objective: text,
        }),
      });

      if (!response.body || !response.ok) {
        throw new Error('Could not connect to the analysis agent');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let boundary = buffer.indexOf('\n\n');
        while (boundary !== -1) {
          const block = buffer.slice(0, boundary);
          buffer = buffer.slice(boundary + 2);
          const lines = block.split('\n');
          let eventName = 'message';
          let payload = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventName = line.replace('event:', '').trim();
            } else if (line.startsWith('data:')) {
              payload += line.replace('data:', '').trim();
            }
          }

          if (!payload) continue;

          const eventData = JSON.parse(payload);

          if (eventName === 'chunk' && typeof eventData.text === 'string') {
            setMessages((current) => {
              const next = [...current];
              const lastIndex = next.length - 1;
              if (lastIndex >= 0 && next[lastIndex].role === 'assistant') {
                next[lastIndex] = {
                  ...next[lastIndex],
                  content: (next[lastIndex].content || '') + eventData.text,
                };
              }
              return next;
            });
          }

          if (eventName === 'dataset_card' && eventData) {
            setDatasetSummary({
              rows: Number(eventData.rows ?? datasetSummary?.rows ?? 0),
              cols: Number(eventData.cols ?? datasetSummary?.cols ?? 0),
              task_type: eventData.task_type,
              target: eventData.target,
              duplicates: Number(eventData.duplicates ?? 0),
              missing_cols: Number(eventData.missing_cols ?? 0),
            });
          }

          if (eventName === 'model_card' && eventData) {
            setModelSummary({
              best_model: eventData.best_model,
              task_type: eventData.task_type,
              metrics: eventData.metrics,
            });
          }

          if (eventName === 'chart' && eventData?.src) {
            const chartImage: GeneratedImage = {
              id: crypto.randomUUID(),
              prompt: eventData.caption || 'Dataset visualization',
              url: eventData.src,
              createdAt: new Date().toISOString(),
              status: 'ready',
            };
            setChartFrames((current) => [
              ...current,
              {
                type: eventData.type || 'image',
                src: eventData.src,
                caption: eventData.caption || 'Visualization',
              },
            ]);
            setGeneratedImages((current) => [chartImage, ...current]);
          }

          if (eventName === 'progress') {
            setStatusText(eventData.label || 'Running analysis...');
          }

          if (eventName === 'done') {
            setStatusText('Analysis complete');
            await loadConversations();
          }

          if (eventName === 'error') {
            setStatusText(eventData.message || 'Analysis failed');
          }

          boundary = buffer.indexOf('\n\n');
        }
      }
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : 'Connection error');
    } finally {
      setIsStreaming(false);
    }
  };

  const visibleConversations = conversations.filter((conversation) =>
    conversation.title.toLowerCase().includes(search.toLowerCase()),
  );

  const displayTitle = conversations.find((item) => item.id === activeConversationId)?.title || 'Chat history';

  const handleNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setDatasetSummary(null);
    setModelSummary(null);
    setChartFrames([]);
    setUploadInfo(null);
    setStatusText('');
    setInput('');
    setActiveSidebarView(null);
    setActiveMode('Chat');
  };

  const handleSidebarView = (view: string) => {
    if (view === 'Home') {
      handleNewChat();
      return;
    }
    if (view === 'Explore') {
      setActiveMode('Work');
      setActiveSidebarView(null);
      setMessages([]);
      setActiveConversationId(null);
      setStatusText('Explore ready');
      return;
    }
    setActiveMode('Work');
    setActiveSidebarView(view);
    setMessages([]);
    setDatasetSummary(null);
    setModelSummary(null);
    setChartFrames([]);
    setUploadInfo(null);
    setActiveConversationId(null);
    setStatusText(`${view} ready`);
  };

  const getConversationTitle = (conversation: Conversation) => {
    const title = conversation.title.trim();
    return title && title.toLowerCase() !== 'new analysis' ? title : 'Chat history';
  };

  const handleModeChange = (mode: 'Chat' | 'Work') => {
    setActiveMode(mode);
    setActiveSidebarView(null);
    if (mode === 'Work') {
      setMessages([]);
      setActiveConversationId(null);
      setStatusText('Work overview ready');
    } else {
      setStatusText('Ready to chat');
    }
  };

  const addProject = () => {
    const name = projectName.trim();
    if (!name) return;
    setProjects((current) => [...current, { id: crypto.randomUUID(), name, createdAt: new Date().toISOString() }]);
    setProjectName('');
  };

  const addTask = () => {
    const title = taskTitle.trim();
    if (!title) return;
    setTasks((current) => [...current, { id: crypto.randomUUID(), title, project: taskProject.trim(), status: 'Todo' }]);
    setTaskTitle('');
    setTaskProject('');
  };

  const addSchedule = () => {
    const name = scheduleName.trim();
    if (!name || !scheduleDate) return;
    setSchedules((current) => [...current, { id: crypto.randomUUID(), name, date: scheduleDate, frequency: scheduleFrequency }]);
    setScheduleName('');
    setScheduleDate('');
    setScheduleFrequency('Once');
  };

  const toggleTask = (taskId: string) => {
    setTasks((current) => current.map((task) => task.id === taskId ? { ...task, status: task.status === 'Todo' ? 'Done' : 'Todo' } : task));
  };

  const deleteWorkspaceItem = (view: string, id: string) => {
    if (view === 'Projects') setProjects((current) => current.filter((item) => item.id !== id));
    if (view === 'Tasks') setTasks((current) => current.filter((item) => item.id !== id));
    if (view === 'Scheduled') setSchedules((current) => current.filter((item) => item.id !== id));
  };

  const generateImage = () => {
    const prompt = imagePrompt.trim();
    if (!prompt || generatingImage) return;
    setGeneratingImage(true);
    const image = {
      id: crypto.randomUUID(),
      prompt,
      url: apiPath(`/api/images/generate?prompt=${encodeURIComponent(prompt)}&seed=${imageSeed()}`),
      createdAt: new Date().toISOString(),
      status: 'loading' as const,
    };
    setGeneratedImages((current) => [image, ...current]);
    setImagePrompt('');
    setGeneratingImage(false);
  };

  const deleteImage = (imageId: string) => {
    setGeneratedImages((current) => current.filter((image) => image.id !== imageId));
  };

  const updateImageStatus = (imageId: string, status: 'ready' | 'error') => {
    setGeneratedImages((current) => current.map((image) => image.id === imageId ? { ...image, status } : image));
  };

  const retryImage = (image: GeneratedImage) => {
    setGeneratedImages((current) => current.map((item) => item.id === image.id ? {
      ...item,
      status: 'loading',
      url: apiPath(`/api/images/generate?prompt=${encodeURIComponent(item.prompt)}&seed=${imageSeed()}`),
    } : item));
  };

  const renderImageCard = (image: GeneratedImage) => (
    <div className="image-card" key={image.id}>
      <div className={`image-preview ${image.status === 'loading' ? 'is-loading' : ''}`}>
        {image.status === 'loading' && <span>Generating image...</span>}
        {image.status === 'error' && <span>Image could not load. <button className="retry-image" onClick={() => retryImage(image)}>Retry</button></span>}
        <img src={image.url} alt={image.prompt} onLoad={() => updateImageStatus(image.id, 'ready')} onError={() => updateImageStatus(image.id, 'error')} />
      </div>
      <div><span>{image.prompt}</span><button className="item-delete" onClick={() => deleteImage(image.id)} aria-label={`Delete ${image.prompt}`}>×</button></div>
    </div>
  );

  const renderWorkspaceView = () => {
    if (activeSidebarView === 'Images') return (
      <div className="workspace-view image-workspace">
        <div className="workspace-heading"><div><h1>Create images</h1><p>Describe an image and WALL E will generate it for your Library.</p></div></div>
        <div className="workspace-form"><input value={imagePrompt} onChange={(event) => setImagePrompt(event.target.value)} placeholder="A watercolor sunset over the mountains" onKeyDown={(event) => { if (event.key === 'Enter') generateImage(); }} /><button className="tool-primary" onClick={generateImage} disabled={generatingImage}>{generatingImage ? 'Generating...' : 'Generate image'}</button></div>
        <p className="image-note">Generated images use the Pollinations image service and may take a moment to load.</p>
        {generatedImages.length > 0 && <div className="image-grid">{generatedImages.slice(0, 4).map(renderImageCard)}</div>}
      </div>
    );
    if (activeSidebarView === 'Library') return (
      <div className="workspace-view image-workspace">
        <div className="workspace-heading"><div><h1>Library</h1><p>Your generated images and saved visual work.</p></div></div>
        {generatedImages.length ? <div className="image-grid">{generatedImages.map(renderImageCard)}</div> : <div className="empty-library"><p>Your Library is empty.</p><button className="tool-primary" onClick={() => handleSidebarView('Images')}>Create an image</button></div>}
      </div>
    );
    if (activeSidebarView === 'Projects') return (
      <div className="workspace-view">
        <div className="workspace-heading"><div><h1>Projects</h1><p>Keep related analysis work together.</p></div></div>
        <div className="workspace-form"><input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="Project name" onKeyDown={(event) => { if (event.key === 'Enter') addProject(); }} /><button className="tool-primary" onClick={addProject}>Add project</button></div>
        <div className="workspace-list">{projects.length ? projects.map((project) => <div className="workspace-item" key={project.id}><strong>{project.name}</strong><button className="item-delete" onClick={() => deleteWorkspaceItem('Projects', project.id)} aria-label={`Delete ${project.name}`}>×</button></div>) : <p className="empty-state">No projects yet.</p>}</div>
      </div>
    );
    if (activeSidebarView === 'Tasks') return (
      <div className="workspace-view">
        <div className="workspace-heading"><div><h1>Tasks</h1><p>Track the next actions for your analysis.</p></div></div>
        <div className="workspace-form workspace-form-wide"><input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Task name" /><input value={taskProject} onChange={(event) => setTaskProject(event.target.value)} placeholder="Project (optional)" /><button className="tool-primary" onClick={addTask}>Add task</button></div>
        <div className="workspace-list">{tasks.length ? tasks.map((task) => <div className="workspace-item" key={task.id}><button className={`task-check ${task.status === 'Done' ? 'complete' : ''}`} onClick={() => toggleTask(task.id)} aria-label={`Mark ${task.title} ${task.status === 'Todo' ? 'done' : 'todo'}`}>{task.status === 'Done' ? '✓' : ''}</button><div><strong className={task.status === 'Done' ? 'task-done' : ''}>{task.title}</strong>{task.project && <small>{task.project}</small>}</div><button className="item-delete" onClick={() => deleteWorkspaceItem('Tasks', task.id)} aria-label={`Delete ${task.title}`}>×</button></div>) : <p className="empty-state">No tasks yet.</p>}</div>
      </div>
    );
    if (activeSidebarView === 'Scheduled') return (
      <div className="workspace-view">
        <div className="workspace-heading"><div><h1>Scheduled</h1><p>Plan recurring analysis work and reminders.</p></div></div>
        <div className="workspace-form workspace-form-wide"><input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)} placeholder="Schedule name" /><input type="datetime-local" value={scheduleDate} onChange={(event) => setScheduleDate(event.target.value)} /><select value={scheduleFrequency} onChange={(event) => setScheduleFrequency(event.target.value)}><option>Once</option><option>Daily</option><option>Weekly</option><option>Monthly</option></select><button className="tool-primary" onClick={addSchedule}>Add schedule</button></div>
        <div className="workspace-list">{schedules.length ? schedules.map((schedule) => <div className="workspace-item" key={schedule.id}><div><strong>{schedule.name}</strong><small>{new Date(schedule.date).toLocaleString()} · {schedule.frequency}</small></div><button className="item-delete" onClick={() => deleteWorkspaceItem('Scheduled', schedule.id)} aria-label={`Delete ${schedule.name}`}>×</button></div>) : <p className="empty-state">No schedules yet.</p>}</div>
      </div>
    );
    return null;
  };

  const slideCapabilities = (direction: number) => {
    capabilityScroller.current?.scrollBy({ left: direction * 260, behavior: 'smooth' });
  };

  return (
    <div className="chatgpt-shell">
      <div className="ambient-robots" aria-hidden="true">
        <div className="ambient-robot robot-one"><span className="robot-antenna" /><span className="robot-eye left" /><span className="robot-eye right" /><span className="robot-mouth" /></div>
        <div className="ambient-robot robot-two"><span className="robot-antenna" /><span className="robot-eye left" /><span className="robot-eye right" /><span className="robot-mouth" /></div>
        <div className="ambient-robot robot-three"><span className="robot-antenna" /><span className="robot-eye left" /><span className="robot-eye right" /><span className="robot-mouth" /></div>
      </div>
      <div className="ai-glow-network" aria-hidden="true">
        <div className="ai-core"><span>AI</span></div>
        <span className="ai-node node-one" />
        <span className="ai-node node-two" />
        <span className="ai-node node-three" />
        <span className="ai-node node-four" />
        <span className="ai-beam beam-one" />
        <span className="ai-beam beam-two" />
        <span className="ai-beam beam-three" />
        <span className="ai-beam beam-four" />
      </div>
      <div className="ambient-particles" aria-hidden="true">
        <span /><span /><span /><span /><span /><span /><span /><span />
      </div>
      <aside className="sidebar-panel">
        <div className="sidebar-top-row">
          <div className="brand-lockup">
            <div className="brand-title">WALL E</div>
            <span>AI WORKSPACE</span>
          </div>
        </div>

        <button className="nav-action" onClick={handleNewChat}>
          <span>New conversation</span>
        </button>

        <div className="nav-list">
          {sidebarItems.map((item) => (
            <button key={item} className={`nav-item ${item === 'Home' && !activeSidebarView && activeMode === 'Chat' ? 'selected' : activeSidebarView === item ? 'selected' : ''}`} onClick={() => handleSidebarView(item)}>
              <span className="nav-icon">{item === 'Home' ? '⌂' : item === 'Images' ? '◍' : item === 'Library' ? '▣' : item === 'Scheduled' ? '◔' : item === 'Tasks' ? '✓' : '▤'}</span>
              <span>{item}</span>
            </button>
          ))}
        </div>

        <div className="sidebar-divider" />

        <div className="recents-label">Recents</div>
        <div className="recent-list">
            {(visibleConversations.length ? visibleConversations : recents).map((item, index) => {
            const title = typeof item === 'string' ? item : item.title;
            const id = typeof item === 'string' ? `${title}-${index}` : item.id;

            return (
              <div key={id} className="recent-row">
                <button className="recent-item" onClick={() => {
                  if (typeof item !== 'string') {
                    setActiveSidebarView(null);
                    setActiveConversationId(item.id);
                  }
                }}>
                  {typeof item === 'string' ? title : getConversationTitle(item)}
                </button>
                {typeof item !== 'string' && <button className="recent-delete" onClick={() => void deleteConversation(item.id)} aria-label={`Delete ${getConversationTitle(item)}`}>×</button>}
              </div>
            );
          })}
        </div>
      </aside>

      <main className="main-panel">
        <header className="main-header">
          <div className="mode-toggle">
            <button className={`mode-btn ${activeMode === 'Chat' ? 'active' : ''}`} onClick={() => handleModeChange('Chat')}>Chat</button>
            <button className={`mode-btn ${activeMode === 'Work' ? 'active' : ''}`} onClick={() => handleModeChange('Work')}>Work</button>
          </div>
        </header>

        <section className="center-stage">
          {activeMode === 'Work' && !activeSidebarView && (
            <div className="work-overview">
              <div className="workspace-heading"><div><h1>Work</h1><p>Manage your analysis projects, tasks, and schedules.</p></div></div>
              <div className="work-cards">
                <button className="work-card" onClick={() => handleSidebarView('Projects')}><strong>Projects</strong><span>{projects.length} {projects.length === 1 ? 'project' : 'projects'}</span></button>
                <button className="work-card" onClick={() => handleSidebarView('Tasks')}><strong>Tasks</strong><span>{tasks.filter((task) => task.status === 'Todo').length} open</span></button>
                <button className="work-card" onClick={() => handleSidebarView('Scheduled')}><strong>Scheduled</strong><span>{schedules.length} {schedules.length === 1 ? 'schedule' : 'schedules'}</span></button>
              </div>
              <button className="tool-primary" onClick={() => handleModeChange('Chat')}>Open chat</button>
            </div>
          )}

          {activeSidebarView && ['Images', 'Library', 'Projects', 'Tasks', 'Scheduled'].includes(activeSidebarView) && !messages.length && !isStreaming && renderWorkspaceView()}

          {activeSidebarView && !['Images', 'Library', 'Projects', 'Tasks', 'Scheduled'].includes(activeSidebarView) && !messages.length && !isStreaming && (
            <div className="tool-view">
              <div className="tool-view-icon">{activeSidebarView === 'Images' ? '◍' : activeSidebarView === 'Library' ? '▣' : activeSidebarView === 'Scheduled' ? '◔' : '▤'}</div>
              <h1>{activeSidebarView}</h1>
              <p>{activeSidebarView === 'Images' ? 'Create and explore visual work here.' : activeSidebarView === 'Library' ? 'Your generated reports and saved work will appear here.' : activeSidebarView === 'Scheduled' ? 'Scheduled analysis tasks will appear here.' : 'Organize your analysis work into projects here.'}</p>
              <button className="tool-primary" onClick={handleNewChat}>Start a new chat</button>
            </div>
          )}

          {activeMode === 'Chat' && !activeSidebarView && !messages.length && !isStreaming && (
            <>
              <div className="welcome-block">
                <div className="welcome-title">Welcome to <span>AI Agent</span></div>
                <p>How can I help you today?</p>
              </div>

              <div className="composer-box">
                <div className="prompt-row">
                  <label className="plus-sign upload-trigger" aria-label="Upload file" title="Upload file">
                    ＋
                    <input type="file" accept=".csv,.xlsx,.xls,.json,.jsonl,.parquet,.feather,.pdf,.docx,.txt,.md,.mp4" onChange={handleFileUpload} />
                  </label>
                  <textarea
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder="Ask anything"
                    rows={1}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        void sendMessage();
                      }
                    }}
                  />
                  <div className="composer-actions">
                    <button className="composer-tool" onClick={() => setInput('Search the web: ')} aria-label="Search the web">◎ <span>Search the web</span></button>
                    <button className="composer-tool" onClick={() => setInput('Reason through: ')} aria-label="Reason">♧ <span>Reason</span></button>
                    <button className="composer-tool" onClick={() => setInput('Write code for: ')} aria-label="Code">&lt;/&gt; <span>Code</span></button>
                    <button className="composer-microphone" onClick={() => setStatusText('Voice input is ready')} aria-label="Voice input">◉</button>
                    <button className="send-pill" onClick={() => void sendMessage()} disabled={isStreaming}>↑</button>
                  </div>
                </div>
              </div>

              <div className="home-actions">
                {[
                  ['Create a graph', () => setInput('Create a graph from this data: '), '▥'],
                  ['Write or edit', () => setInput('Write or edit'), '✎'],
                  ['Analyze data', () => setInput('Analyze this dataset'), '▥'],
                  ['Summarize code', () => setInput('Summarize this code: '), '▤'],
                  ['More', () => setActiveMode('Work'), '•••'],
                ].map(([label, action, icon]) => (
                  <button key={label as string} className="home-action" onClick={action as () => void}>
                    <span>{icon as string}</span>
                    {label as string}
                  </button>
                ))}
              </div>

              <div className="explore-heading-row"><div className="explore-heading">Explore what WALL E can do</div><div className="carousel-controls"><button onClick={() => slideCapabilities(-1)} aria-label="Previous capabilities">‹</button><button onClick={() => slideCapabilities(1)} aria-label="Next capabilities">›</button></div></div>
              <div className="capability-grid" ref={capabilityScroller}>
                {[
                  ['Smart Conversations', 'Get intelligent answers and creative solutions.', '◉'],
                  ['Data Analysis', 'Upload data and uncover powerful insights.', '▥'],
                  ['Image Generation', 'Create stunning images from your ideas.', '◍'],
                  ['Code Assistant', 'Write, debug, and optimize code faster.', '</>'],
                  ['Research & Search', 'Search the web and get relevant information.', '◎'],
                ].map(([title, description, icon]) => (
                  <button key={title} className="capability-card" onClick={() => title === 'Image Generation' ? handleSidebarView('Images') : title === 'Data Analysis' ? setInput('Analyze this dataset') : title === 'Research & Search' ? setInput('Search the web') : setInput(title)}>
                    <span className="capability-icon">{icon}</span>
                    <strong>{title}</strong>
                    <small>{description}</small>
                    <b>›</b>
                  </button>
                ))}
              </div>

            </>
          )}

          {messages.length > 0 && (
            <div className="messages-area">
              <div className="chat-thread-header">{displayTitle}</div>
              {messages.map((message, index) => (
                <div key={`${message.id || index}`} className={`message-row ${message.role}`}>
                  <div className="message-avatar">{message.role === 'assistant' ? 'AI' : 'U'}</div>
                  <div className="message-bubble">
                    <p>{message.content || (message.role === 'assistant' ? 'Thinking...' : '')}</p>
                  </div>
                </div>
              ))}

              {(datasetSummary || modelSummary || chartFrames.length > 0) && (
                <div className="analysis-panel">
                  {datasetSummary && (
                    <div className="insight-grid">
                      <div className="metric-card"><label>Rows</label><strong>{datasetSummary.rows ?? 0}</strong></div>
                      <div className="metric-card"><label>Columns</label><strong>{datasetSummary.cols ?? 0}</strong></div>
                      <div className="metric-card"><label>Target</label><strong>{datasetSummary.target || 'Not detected'}</strong></div>
                      <div className="metric-card"><label>Task</label><strong>{datasetSummary.task_type || 'Unknown'}</strong></div>
                    </div>
                  )}

                  {modelSummary && (
                    <div className="model-panel">
                      <h3>Model results</h3>
                      <div className="model-header">
                        <span>Best model</span>
                        <strong>{modelSummary.best_model || 'Not available'}</strong>
                      </div>
                      <div className="metrics-list">
                        {Object.entries(modelSummary.metrics || {}).map(([key, value]) => (
                          <div key={key} className="metric-row">
                            <span>{key}</span>
                            <strong>{typeof value === 'number' ? value.toFixed(4) : value}</strong>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {chartFrames.length > 0 && (
                    <div className="visual-grid">
                      {chartFrames.map((chart) => (
                        <div key={`${chart.caption}-${chart.src}`} className="visual-card">
                          <img src={chart.src} alt={chart.caption} />
                          <span>{chart.caption}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {(uploadInfo || statusText) && !activeSidebarView && !messages.length && !isStreaming && (
            <div className="status-inline">
              <span>{statusText}</span>
              {uploadInfo && (
                <span>
                  {uploadInfo.name} • {uploadInfo.rows} rows • {uploadInfo.cols} cols
                </span>
              )}
            </div>
          )}
        </section>

      </main>
    </div>
  );
}
