import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
  Play, Pause, Volume2, VolumeX, Maximize, Clock, Eye, ThumbsUp, 
  Share2, Bookmark, CheckCircle, Upload, Film, X, Loader2, 
  AlertCircle, MessageSquare, Send, Trash2, RefreshCw, Edit3
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { 
  apiClient, 
  type VideoResponse, 
  type VideoCommentResponse 
} from '../../services/apiClient';

export const VideoStreamView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();

  // Feed & Selected Video state
  const [videos, setVideos] = useState<VideoResponse[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoResponse | null>(null);
  const [isLoadingFeed, setIsLoadingFeed] = useState<boolean>(true);
  const [feedError, setFeedError] = useState<string | null>(null);

  // HTML5 Video Player state
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [playbackError, setPlaybackError] = useState<string | null>(null);

  // Upload modal state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState<boolean>(false);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadDescription, setUploadDescription] = useState('');
  const [uploadThumbnailUrl, setUploadThumbnailUrl] = useState('');
  const [uploadVisibility, setUploadVisibility] = useState<'public' | 'private'>('public');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<string>('');

  // Video comments state
  const [comments, setComments] = useState<VideoCommentResponse[]>([]);
  const [isLoadingComments, setIsLoadingComments] = useState<boolean>(false);
  const [newCommentText, setNewCommentText] = useState('');
  const [isSubmittingComment, setIsSubmittingComment] = useState<boolean>(false);

  // Related videos state
  const [relatedVideos, setRelatedVideos] = useState<VideoResponse[]>([]);

  // Edit Video Modal state (Owner only)
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editThumbnailUrl, setEditThumbnailUrl] = useState('');
  const [editVisibility, setEditVisibility] = useState<'public' | 'private'>('public');
  const [isSavingEdit, setIsSavingEdit] = useState<boolean>(false);

  // Fetch Videos Feed
  const fetchVideos = useCallback(async () => {
    setIsLoadingFeed(true);
    setFeedError(null);
    try {
      const data = await apiClient.listVideos(25);
      setVideos(data);
      if (data.length > 0 && !selectedVideo) {
        setSelectedVideo(data[0]);
      }
    } catch (err: any) {
      setFeedError(err.message || 'Failed to load video feed');
    } finally {
      setIsLoadingFeed(false);
    }
  }, [selectedVideo]);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  // Load comments and trigger view record when selected video changes
  useEffect(() => {
    if (!selectedVideo) return;

    // Reset player error
    setPlaybackError(null);
    setIsPlaying(false);

    // Record view after mounting
    apiClient.recordVideoView(selectedVideo.id).catch(() => {});

    // Fetch comments
    setIsLoadingComments(true);
    apiClient
      .listVideoComments(selectedVideo.id)
      .then((c) => setComments(c))
      .catch(() => setComments([]))
      .finally(() => setIsLoadingComments(false));

    // Fetch related videos
    apiClient
      .listRelatedVideos(selectedVideo.id)
      .then((rel) => setRelatedVideos(rel))
      .catch(() => setRelatedVideos([]));
  }, [selectedVideo?.id]);

  // Player controls
  const handleTogglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((err) => {
          setPlaybackError('Unable to start playback. Click play again or check format.');
          setIsPlaying(false);
        });
    }
  };

  const handleToggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
    if (!duration && videoRef.current.duration) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    setDuration(videoRef.current.duration);
  };

  const handleFullscreen = () => {
    if (!videoRef.current) return;
    if (videoRef.current.requestFullscreen) {
      videoRef.current.requestFullscreen();
    }
  };

  // Like / Unlike Video with optimistic UI
  const handleToggleLike = async () => {
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    if (!selectedVideo) return;

    const previousLiked = selectedVideo.is_liked;
    const previousLikesCount = selectedVideo.likes_count;

    // Optimistic UI update
    setSelectedVideo({
      ...selectedVideo,
      is_liked: !previousLiked,
      likes_count: previousLiked ? selectedVideo.likes_count - 1 : selectedVideo.likes_count + 1,
    });
    setVideos((prev) =>
      prev.map((v) =>
        v.id === selectedVideo.id
          ? {
              ...v,
              is_liked: !previousLiked,
              likes_count: previousLiked ? v.likes_count - 1 : v.likes_count + 1,
            }
          : v
      )
    );

    try {
      if (previousLiked) {
        const res = await apiClient.unlikeVideo(selectedVideo.id);
        setSelectedVideo((curr) => curr && { ...curr, likes_count: res.likes_count, is_liked: res.is_liked });
      } else {
        const res = await apiClient.likeVideo(selectedVideo.id);
        setSelectedVideo((curr) => curr && { ...curr, likes_count: res.likes_count, is_liked: res.is_liked });
      }
    } catch {
      // Rollback on failure
      setSelectedVideo((curr) => curr && { ...curr, is_liked: previousLiked, likes_count: previousLikesCount });
      setVideos((prev) =>
        prev.map((v) =>
          v.id === selectedVideo.id
            ? { ...v, is_liked: previousLiked, likes_count: previousLikesCount }
            : v
        )
      );
    }
  };

  // Add Comment
  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    if (!selectedVideo || !newCommentText.trim() || isSubmittingComment) return;

    setIsSubmittingComment(true);
    try {
      const created = await apiClient.addVideoComment(selectedVideo.id, newCommentText.trim());
      setComments((prev) => [...prev, created]);
      setNewCommentText('');
      setSelectedVideo((curr) => curr && { ...curr, comments_count: curr.comments_count + 1 });
    } catch (err: any) {
      alert(err.message || 'Failed to submit comment');
    } finally {
      setIsSubmittingComment(false);
    }
  };

  // Edit Video Metadata (Owner only)
  const handleOpenEdit = (v: VideoResponse) => {
    setEditTitle(v.title);
    setEditDescription(v.description || '');
    setEditThumbnailUrl(v.thumbnail_url || '');
    setEditVisibility(v.visibility);
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedVideo || !editTitle.trim() || isSavingEdit) return;

    setIsSavingEdit(true);
    try {
      const updated = await apiClient.updateVideo(selectedVideo.id, {
        title: editTitle.trim(),
        description: editDescription.trim() || undefined,
        thumbnail_url: editThumbnailUrl.trim() || undefined,
        visibility: editVisibility,
      });
      setSelectedVideo((curr) => curr && { ...curr, ...updated });
      setVideos((prev) => prev.map((v) => (v.id === selectedVideo.id ? { ...v, ...updated } : v)));
      setIsEditModalOpen(false);
    } catch (err: any) {
      alert(err.message || 'Failed to update video metadata');
    } finally {
      setIsSavingEdit(false);
    }
  };

  // Delete Video (Owner only)
  const handleDeleteVideo = async (videoId: string) => {
    if (!confirm('Are you sure you want to delete this video? This cannot be undone.')) return;
    try {
      await apiClient.deleteVideo(videoId);
      setVideos((prev) => prev.filter((v) => v.id !== videoId));
      if (selectedVideo?.id === videoId) {
        const remaining = videos.filter((v) => v.id !== videoId);
        setSelectedVideo(remaining.length > 0 ? remaining[0] : null);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete video');
    }
  };

  // Handle Video Upload
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      alert('Please select a video file (MP4, WebM, Ogg, QuickTime)');
      return;
    }

    setIsUploading(true);
    setUploadProgress('Uploading video stream to storage...');

    const formData = new FormData();
    formData.append('title', uploadTitle.trim());
    if (uploadDescription.trim()) formData.append('description', uploadDescription.trim());
    if (uploadThumbnailUrl.trim()) formData.append('thumbnail_url', uploadThumbnailUrl.trim());
    formData.append('visibility', uploadVisibility);
    formData.append('file', selectedFile);

    try {
      const created = await apiClient.uploadVideo(formData);
      setVideos((prev) => [created, ...prev]);
      setSelectedVideo(created);
      setIsUploadModalOpen(false);
      // Reset form
      setUploadTitle('');
      setUploadDescription('');
      setUploadThumbnailUrl('');
      setSelectedFile(null);
      setUploadProgress('');
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const formatSeconds = (sec: number) => {
    if (isNaN(sec) || !isFinite(sec)) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto w-full pb-12">
      {/* Top Bar with Upload Button */}
      <div className="flex items-center justify-between p-4 rounded-2xl bg-slate-900/60 border border-white/10 backdrop-blur-md">
        <div className="flex items-center space-x-2.5">
          <Film className="w-5 h-5 text-violet-400" />
          <h2 className="text-sm font-bold text-white tracking-wide">SUPER_AI Video Network</h2>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchVideos}
            disabled={isLoadingFeed}
            className="p-2 text-slate-400 hover:text-white rounded-xl hover:bg-white/5 transition"
            title="Refresh stream"
          >
            <RefreshCw className={`w-4 h-4 ${isLoadingFeed ? 'animate-spin text-violet-400' : ''}`} />
          </button>
          <button
            onClick={() => {
              if (!isAuthenticated) {
                openLoginModal();
                return;
              }
              setIsUploadModalOpen(true);
            }}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition shadow"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Video</span>
          </button>
        </div>
      </div>

      {/* Status Messages */}
      {feedError && (
        <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{feedError}</span>
        </div>
      )}

      {/* Main Video Player Screen */}
      {selectedVideo ? (
        <div className="rounded-3xl overflow-hidden border border-white/10 bg-black/90 backdrop-blur-md shadow-2xl">
          <div className="relative aspect-video w-full bg-black flex items-center justify-center group overflow-hidden">
            {/* HTML5 Native Video Tag with HTTP Range Streaming */}
            <video
              ref={videoRef}
              src={apiClient.getVideoStreamUrl(selectedVideo.id)}
              poster={selectedVideo.thumbnail_url || undefined}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onError={() => setPlaybackError('Video media stream encountered an error or format issue')}
              playsInline
              className="w-full h-full object-contain"
            />

            {playbackError && (
              <div className="absolute inset-0 bg-black/80 flex flex-col items-center justify-center p-4 text-center space-y-2 z-20">
                <AlertCircle className="w-8 h-8 text-rose-400" />
                <p className="text-xs text-rose-300">{playbackError}</p>
                <button
                  onClick={() => {
                    setPlaybackError(null);
                    if (videoRef.current) {
                      videoRef.current.load();
                      videoRef.current.play().catch(() => {});
                    }
                  }}
                  className="px-3 py-1 bg-white/10 hover:bg-white/20 rounded-lg text-xs text-white"
                >
                  Retry Stream
                </button>
              </div>
            )}

            {/* Custom Bottom Controls Bar */}
            <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/90 via-black/50 to-transparent flex items-center justify-between text-white text-xs z-10 opacity-90 hover:opacity-100 transition-opacity">
              <div className="flex items-center space-x-3">
                <button
                  type="button"
                  onClick={handleTogglePlay}
                  className="p-1 hover:text-violet-400 transition"
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>
                <button
                  type="button"
                  onClick={handleToggleMute}
                  className="p-1 hover:text-violet-400 transition"
                >
                  {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                </button>
                <span className="font-mono text-[11px] text-slate-300">
                  {formatSeconds(currentTime)} / {formatSeconds(duration || 0)}
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <span className="px-2 py-0.5 rounded bg-white/20 font-mono text-[10px] uppercase">
                  {selectedVideo.mime_type.replace('video/', '')}
                </span>
                <button type="button" onClick={handleFullscreen} className="p-1 hover:text-violet-400 transition">
                  <Maximize className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Video Metadata & Actions */}
          <div className="p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-lg md:text-xl font-bold text-white tracking-tight">{selectedVideo.title}</h1>
                <p className="text-xs text-slate-400 mt-1 flex items-center space-x-2">
                  <span>{selectedVideo.view_count} views</span>
                  <span>•</span>
                  <span>{new Date(selectedVideo.created_at).toLocaleDateString()}</span>
                  {selectedVideo.visibility === 'private' && (
                    <>
                      <span>•</span>
                      <span className="text-amber-400 font-semibold">[Private Video]</span>
                    </>
                  )}
                </p>
              </div>

              {selectedVideo.is_owner && (
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => handleOpenEdit(selectedVideo)}
                    className="px-3 py-1.5 bg-violet-500/10 hover:bg-violet-500/20 text-violet-300 rounded-xl text-xs font-semibold flex items-center space-x-1.5 border border-violet-500/20 transition"
                    title="Edit video metadata"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    <span>Edit</span>
                  </button>
                  <button
                    onClick={() => handleDeleteVideo(selectedVideo.id)}
                    className="px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 rounded-xl text-xs font-semibold flex items-center space-x-1.5 border border-rose-500/20 transition"
                    title="Delete this video"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete</span>
                  </button>
                </div>
              )}
            </div>

            {selectedVideo.description && (
              <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap bg-white/5 p-3 rounded-xl border border-white/5">
                {selectedVideo.description}
              </p>
            )}

            {/* Creator Bar & Interactive Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-white/10">
              <div className="flex items-center space-x-3">
                {selectedVideo.owner_avatar ? (
                  <img
                    src={selectedVideo.owner_avatar}
                    alt={selectedVideo.owner_full_name}
                    className="w-10 h-10 rounded-full object-cover border border-white/10"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-violet-600 to-indigo-600 flex items-center justify-center font-bold text-xs text-white uppercase">
                    {selectedVideo.owner_username.slice(0, 2)}
                  </div>
                )}
                <div>
                  <h4 className="text-sm font-semibold text-white flex items-center gap-1.5">
                    {selectedVideo.owner_full_name}
                    <CheckCircle className="w-3.5 h-3.5 text-violet-400" />
                  </h4>
                  <p className="text-[11px] text-slate-400">@{selectedVideo.owner_username}</p>
                </div>
              </div>

              <div className="flex items-center space-x-2 text-xs">
                <button
                  onClick={handleToggleLike}
                  className={`px-4 py-2 rounded-xl flex items-center gap-1.5 transition ${
                    selectedVideo.is_liked
                      ? 'bg-pink-600 text-white font-semibold'
                      : 'bg-white/10 hover:bg-white/15 text-white'
                  }`}
                >
                  <ThumbsUp className={`w-4 h-4 ${selectedVideo.is_liked ? 'fill-current' : ''}`} />
                  <span>{selectedVideo.likes_count}</span>
                </button>

                <button
                  onClick={() => {
                    navigator.clipboard.writeText(window.location.href);
                    alert('Video link copied to clipboard!');
                  }}
                  className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-white flex items-center gap-1.5 transition"
                >
                  <Share2 className="w-4 h-4" />
                  <span>Share</span>
                </button>
              </div>
            </div>

            {/* Comments Thread Section */}
            <div className="pt-4 border-t border-white/10 space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <MessageSquare className="w-4 h-4 text-violet-400" />
                <span>Comments ({comments.length})</span>
              </h3>

              {/* Comment Input */}
              <form onSubmit={handleAddComment} className="flex items-center space-x-2">
                <input
                  type="text"
                  placeholder={isAuthenticated ? "Add a public comment..." : "Sign in to leave a comment"}
                  value={newCommentText}
                  onChange={(e) => setNewCommentText(e.target.value)}
                  disabled={isSubmittingComment}
                  maxLength={500}
                  className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500"
                />
                <button
                  type="submit"
                  disabled={!newCommentText.trim() || isSubmittingComment}
                  className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold disabled:opacity-40 transition flex items-center space-x-1"
                >
                  {isSubmittingComment ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  <span>Comment</span>
                </button>
              </form>

              {/* Comment Items */}
              <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                {isLoadingComments ? (
                  <div className="flex justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin text-violet-400" />
                  </div>
                ) : comments.length === 0 ? (
                  <p className="text-xs text-slate-500 py-2">No comments yet. Be the first to share your thoughts!</p>
                ) : (
                  comments.map((comment) => (
                    <div key={comment.id} className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center space-x-2">
                          <span className="font-semibold text-slate-200">{comment.author_full_name}</span>
                          <span className="text-[10px] text-slate-500">@{comment.author_username}</span>
                        </div>
                        <span className="text-[10px] text-slate-500">
                          {new Date(comment.created_at).toLocaleDateString()}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 whitespace-pre-wrap">{comment.content}</p>
                    </div>
                  ))
                )}
              </div>

              {/* Related Videos Section */}
              {relatedVideos.length > 0 && (
                <div className="pt-4 border-t border-white/10 space-y-3">
                  <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                    <Film className="w-3.5 h-3.5 text-pink-400" />
                    <span>Related Videos</span>
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {relatedVideos.map((rel) => (
                      <div
                        key={rel.id}
                        onClick={() => {
                          setSelectedVideo(rel);
                          window.scrollTo({ top: 0, behavior: 'smooth' });
                        }}
                        className="flex items-center space-x-3 p-2.5 rounded-xl bg-white/5 border border-white/5 hover:border-violet-500/30 cursor-pointer transition group"
                      >
                        <div className="w-24 aspect-video bg-black rounded-lg overflow-hidden shrink-0 flex items-center justify-center">
                          {rel.thumbnail_url ? (
                            <img src={rel.thumbnail_url} alt={rel.title} className="w-full h-full object-cover" />
                          ) : (
                            <Film className="w-5 h-5 text-slate-600" />
                          )}
                        </div>
                        <div className="overflow-hidden">
                          <h5 className="text-xs font-semibold text-slate-200 truncate group-hover:text-violet-300 transition">
                            {rel.title}
                          </h5>
                          <p className="text-[10px] text-slate-400 truncate">{rel.owner_full_name}</p>
                          <p className="text-[10px] text-slate-500">{rel.view_count} views</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-20 bg-slate-900/40 rounded-3xl border border-white/5 p-8 space-y-3">
          <Film className="w-12 h-12 text-slate-600 mx-auto" />
          <h3 className="text-sm font-semibold text-slate-300">No Videos Published Yet</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Be the first creator to upload a technical walkthrough, talk, or demo to the platform.
          </p>
        </div>
      )}

      {/* Up Next & Recommended Grid */}
      <div className="space-y-4">
        <h3 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">
          Platform Video Feed ({videos.length})
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {videos.map((v) => {
            const isCurrent = selectedVideo?.id === v.id;
            return (
              <div
                key={v.id}
                onClick={() => {
                  setSelectedVideo(v);
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                className={`rounded-2xl overflow-hidden border transition-all cursor-pointer group bg-slate-900/40 ${
                  isCurrent ? 'border-violet-500 ring-2 ring-violet-500/20' : 'border-white/5 hover:border-violet-500/40'
                }`}
              >
                <div className="relative aspect-video w-full bg-slate-950 flex items-center justify-center overflow-hidden">
                  {v.thumbnail_url ? (
                    <img
                      src={v.thumbnail_url}
                      alt={v.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center bg-violet-950/20 text-violet-400">
                      <Film className="w-8 h-8 opacity-60" />
                    </div>
                  )}
                  <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/80 text-[10px] text-white font-mono uppercase">
                    {v.mime_type.replace('video/', '')}
                  </span>
                </div>
                <div className="p-3.5 space-y-1">
                  <h4 className="text-xs font-semibold text-slate-200 line-clamp-2 group-hover:text-violet-300 transition">
                    {v.title}
                  </h4>
                  <p className="text-[11px] text-slate-400">{v.owner_full_name}</p>
                  <p className="text-[10px] text-slate-500">
                    {v.view_count} views • {new Date(v.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* EDIT VIDEO MODAL (OWNER ONLY) */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Edit3 className="w-4 h-4 text-violet-400" />
                <span>Edit Video Metadata</span>
              </h3>
              <button
                type="button"
                onClick={() => !isSavingEdit && setIsEditModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-3.5">
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Title</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  disabled={isSavingEdit}
                  maxLength={150}
                  required
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Description</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  disabled={isSavingEdit}
                  rows={3}
                  maxLength={2000}
                  className="w-full bg-slate-800 border border-white/10 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Thumbnail URL</label>
                <input
                  type="url"
                  placeholder="https://..."
                  value={editThumbnailUrl}
                  onChange={(e) => setEditThumbnailUrl(e.target.value)}
                  disabled={isSavingEdit}
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Visibility</label>
                <select
                  value={editVisibility}
                  onChange={(e) => setEditVisibility(e.target.value as any)}
                  disabled={isSavingEdit}
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                >
                  <option value="public">Public (Everyone can stream)</option>
                  <option value="private">Private (Only you can stream)</option>
                </select>
              </div>

              <div className="flex justify-end space-x-2 pt-2 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setIsEditModalOpen(false)}
                  disabled={isSavingEdit}
                  className="px-4 py-2 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSavingEdit || !editTitle.trim()}
                  className="px-5 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold disabled:opacity-50 transition flex items-center space-x-1.5 shadow"
                >
                  {isSavingEdit ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Changes</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* UPLOAD VIDEO MODAL */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Upload className="w-4 h-4 text-violet-400" />
                <span>Upload Video Stream</span>
              </h3>
              <button
                type="button"
                onClick={() => !isUploading && setIsUploadModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-3.5">
              <div className="space-y-1">
                <label className="text-xs text-slate-400">Video File (MP4, WebM, Ogg, QuickTime - Max 100MB)</label>
                <input
                  type="file"
                  accept="video/mp4,video/webm,video/ogg,video/quicktime"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  disabled={isUploading}
                  required
                  className="w-full text-xs text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-violet-600 file:text-white hover:file:bg-violet-500 cursor-pointer bg-slate-800/80 p-2 rounded-xl border border-white/10"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Title</label>
                <input
                  type="text"
                  placeholder="e.g. Deep dive into Indic multi-modal inference"
                  value={uploadTitle}
                  onChange={(e) => setUploadTitle(e.target.value)}
                  disabled={isUploading}
                  maxLength={150}
                  required
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Description (Optional)</label>
                <textarea
                  placeholder="What is this video about?"
                  value={uploadDescription}
                  onChange={(e) => setUploadDescription(e.target.value)}
                  disabled={isUploading}
                  rows={2}
                  maxLength={2000}
                  className="w-full bg-slate-800 border border-white/10 rounded-xl p-2.5 text-xs text-slate-200 focus:outline-none focus:border-violet-500 resize-none"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Thumbnail Image URL (Optional)</label>
                <input
                  type="url"
                  placeholder="https://..."
                  value={uploadThumbnailUrl}
                  onChange={(e) => setUploadThumbnailUrl(e.target.value)}
                  disabled={isUploading}
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs text-slate-400">Visibility</label>
                <select
                  value={uploadVisibility}
                  onChange={(e) => setUploadVisibility(e.target.value as any)}
                  disabled={isUploading}
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                >
                  <option value="public">Public (Everyone can stream)</option>
                  <option value="private">Private (Only you can stream)</option>
                </select>
              </div>

              {uploadProgress && (
                <div className="p-2.5 rounded-xl bg-violet-600/10 border border-violet-500/20 text-violet-300 text-xs flex items-center space-x-2">
                  <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                  <span>{uploadProgress}</span>
                </div>
              )}

              <div className="flex justify-end space-x-2 pt-2 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setIsUploadModalOpen(false)}
                  disabled={isUploading}
                  className="px-4 py-2 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUploading || !uploadTitle.trim() || !selectedFile}
                  className="px-5 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold disabled:opacity-50 transition flex items-center space-x-1.5 shadow"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <span>Publish Video</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
