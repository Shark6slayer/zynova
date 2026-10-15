import React, { useState, useEffect, useCallback, useTransition, useRef } from 'react';
import { 
  Heart, MessageCircle, Share2, 
  Image as ImageIcon, Send, MoreHorizontal, UserCheck, UserPlus, 
  AlertCircle, Loader2, Edit3, Trash2, Flag, X, ArrowLeft, RefreshCw,
  Compass, Play, Pause, Volume2, VolumeX, Upload, Film, Search, User
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { 
  apiClient, 
  type PostResponse, 
  type CommentResponse, 
  type SocialProfileResponse,
  type UserPublicSummary,
  type SearchResponse
} from '../../services/apiClient';

export const SocialFeedView: React.FC = () => {
  const { user, isAuthenticated, openLoginModal } = useAuth();
  const [, startTransition] = useTransition();

  // Navigation tabs: 'discovery' | 'following' | 'reels' | 'explore' | 'my-profile'
  const [feedMode, setFeedMode] = useState<'discovery' | 'following' | 'reels' | 'explore' | 'my-profile'>('discovery');
  const [posts, setPosts] = useState<PostResponse[]>([]);
  const [isLoadingFeed, setIsLoadingFeed] = useState<boolean>(true);
  const [feedError, setFeedError] = useState<string | null>(null);

  // New post state
  const [newContent, setNewContent] = useState('');
  const [newImageUrl, setNewImageUrl] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [mediaUploadProgress, setMediaUploadProgress] = useState<string | null>(null);
  const [showImageInput, setShowImageInput] = useState(false);
  const [isSubmittingPost, setIsSubmittingPost] = useState(false);

  // Edit post state
  const [editingPostId, setEditingPostId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editImageUrl, setEditImageUrl] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Comment drawer / modal state
  const [activeCommentsPostId, setActiveCommentsPostId] = useState<string | null>(null);
  const [comments, setComments] = useState<CommentResponse[]>([]);
  const [isLoadingComments, setIsLoadingComments] = useState(false);
  const [newCommentText, setNewCommentText] = useState('');
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);

  // Profile modal state
  const [viewingProfileId, setViewingProfileId] = useState<string | null>(null);
  const [profileData, setProfileData] = useState<SocialProfileResponse | null>(null);
  const [profilePosts, setProfilePosts] = useState<PostResponse[]>([]);
  const [isLoadingProfile, setIsLoadingProfile] = useState(false);
  const [isFollowToggling, setIsFollowToggling] = useState(false);
  const [activeFollowListTab, setActiveFollowListTab] = useState<'followers' | 'following' | null>(null);
  const [followListUsers, setFollowListUsers] = useState<UserPublicSummary[]>([]);
  const [isLoadingFollowList, setIsLoadingFollowList] = useState(false);

  // Reels state
  const [activeReelIndex, setActiveReelIndex] = useState<number>(0);
  const [isReelMuted, setIsReelMuted] = useState<boolean>(true);
  const [isReelPlaying, setIsReelPlaying] = useState<boolean>(true);

  // Explore search state
  const [exploreQuery, setExploreQuery] = useState('');
  const [exploreResults, setExploreResults] = useState<SearchResponse | null>(null);
  const [isSearchingExplore, setIsSearchingExplore] = useState(false);

  // Report modal state
  const [reportingTarget, setReportingTarget] = useState<{ id: string; type: 'post' | 'user' | 'comment' } | null>(null);
  const [reportReason, setReportReason] = useState('spam');
  const [reportDescription, setReportDescription] = useState('');
  const [isSubmittingReport, setIsSubmittingReport] = useState(false);
  const [reportSuccessMessage, setReportSuccessMessage] = useState<string | null>(null);

  // Fetch Feed
  const fetchFeed = useCallback(async (mode: 'discovery' | 'following' | 'reels' | 'explore' | 'my-profile') => {
    if (mode === 'explore' || mode === 'my-profile') {
      setIsLoadingFeed(false);
      return;
    }

    setIsLoadingFeed(true);
    setFeedError(null);
    try {
      const data = await apiClient.getSocialFeed(mode as any, 30);
      setPosts(data);
    } catch (err: any) {
      console.error('Social feed fetch error:', err);
      setFeedError(`${err.name || 'Error'}: ${err.message || 'Failed to load feed'} (Endpoint: ${apiClient.getApiBaseUrl()}/social/feed)`);
    } finally {
      setIsLoadingFeed(false);
    }
  }, []);

  useEffect(() => {
    fetchFeed(feedMode);
  }, [feedMode, fetchFeed]);

  // Create Post with File Upload Support
  const handleCreatePost = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    if ((!newContent.trim() && !selectedFile) || isSubmittingPost) return;

    setIsSubmittingPost(true);
    setMediaUploadProgress(null);

    try {
      let uploadedMediaUrl = newImageUrl.trim() || undefined;
      let detectedMediaType: 'image' | 'video' = 'image';

      // If user selected a local file, upload it to /api/v1/social/media
      if (selectedFile) {
        setMediaUploadProgress('Uploading media...');
        const uploadRes = await apiClient.uploadSocialMedia(selectedFile);
        uploadedMediaUrl = uploadRes.media_url;
        detectedMediaType = uploadRes.media_type;
      } else if (uploadedMediaUrl && anyVideoExtension(uploadedMediaUrl)) {
        detectedMediaType = 'video';
      }

      const created = await apiClient.createSocialPost({
        content: newContent.trim() || 'Shared a moment',
        image_url: detectedMediaType === 'image' ? uploadedMediaUrl : undefined,
        media_url: uploadedMediaUrl,
        media_type: detectedMediaType,
      });

      setPosts((prev) => [created, ...prev]);
      setNewContent('');
      setNewImageUrl('');
      setSelectedFile(null);
      setShowImageInput(false);
      setMediaUploadProgress(null);
    } catch (err: any) {
      alert(err.message || 'Failed to publish post');
    } finally {
      setIsSubmittingPost(false);
      setMediaUploadProgress(null);
    }
  };

  const anyVideoExtension = (url: string) => {
    return ['.mp4', '.webm', '.ogg', '.mov'].some((ext) => url.toLowerCase().includes(ext));
  };

  // Edit Post
  const handleStartEdit = (post: PostResponse) => {
    setEditingPostId(post.id);
    setEditContent(post.content);
    setEditImageUrl(post.image_url || '');
  };

  const handleSaveEdit = async (postId: string) => {
    if (!editContent.trim() || isSavingEdit) return;
    setIsSavingEdit(true);
    try {
      const updated = await apiClient.editSocialPost(postId, {
        content: editContent.trim(),
        image_url: editImageUrl.trim() || undefined,
      });
      setPosts((prev) => prev.map((p) => (p.id === postId ? updated : p)));
      setEditingPostId(null);
    } catch (err: any) {
      alert(err.message || 'Failed to update post');
    } finally {
      setIsSavingEdit(false);
    }
  };

  // Delete Post
  const handleDeletePost = async (postId: string) => {
    if (!confirm('Are you sure you want to delete this post?')) return;
    try {
      await apiClient.deleteSocialPost(postId);
      setPosts((prev) => prev.filter((p) => p.id !== postId));
      if (profilePosts.length > 0) {
        setProfilePosts((prev) => prev.filter((p) => p.id !== postId));
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete post');
    }
  };

  // Like / Unlike with optimistic UI
  const handleToggleLike = async (postId: string) => {
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }

    const targetPost = posts.find((p) => p.id === postId);
    if (!targetPost) return;

    const previousLiked = targetPost.is_liked;
    const previousLikesCount = targetPost.likes_count;

    // Optimistic update
    setPosts((prev) =>
      prev.map((p) => {
        if (p.id === postId) {
          return {
            ...p,
            is_liked: !previousLiked,
            likes_count: previousLiked ? p.likes_count - 1 : p.likes_count + 1,
          };
        }
        return p;
      })
    );

    try {
      if (previousLiked) {
        const res = await apiClient.unlikeSocialPost(postId);
        setPosts((prev) =>
          prev.map((p) => (p.id === postId ? { ...p, likes_count: res.likes_count, is_liked: res.is_liked } : p))
        );
      } else {
        const res = await apiClient.likeSocialPost(postId);
        setPosts((prev) =>
          prev.map((p) => (p.id === postId ? { ...p, likes_count: res.likes_count, is_liked: res.is_liked } : p))
        );
      }
    } catch {
      // Rollback on failure
      setPosts((prev) =>
        prev.map((p) =>
          p.id === postId ? { ...p, is_liked: previousLiked, likes_count: previousLikesCount } : p
        )
      );
    }
  };

  // Open Comments Drawer
  const handleOpenComments = async (postId: string) => {
    setActiveCommentsPostId(postId);
    setIsLoadingComments(true);
    try {
      const data = await apiClient.listPostComments(postId);
      setComments(data);
    } catch (err: any) {
      alert(err.message || 'Failed to load comments');
    } finally {
      setIsLoadingComments(false);
    }
  };

  // Submit Comment
  const handleCreateComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    if (!activeCommentsPostId || !newCommentText.trim() || isSubmittingComment) return;

    setIsSubmittingComment(true);
    try {
      const created = await apiClient.createPostComment(activeCommentsPostId, newCommentText.trim());
      setComments((prev) => [created, ...prev]);
      setNewCommentText('');
      // Increment comment count in posts list
      setPosts((prev) =>
        prev.map((p) => (p.id === activeCommentsPostId ? { ...p, comments_count: p.comments_count + 1 } : p))
      );
    } catch (err: any) {
      alert(err.message || 'Failed to submit comment');
    } finally {
      setIsSubmittingComment(false);
    }
  };

  // Delete Comment
  const handleDeleteComment = async (commentId: string) => {
    if (!confirm('Are you sure you want to delete this comment?')) return;
    try {
      await apiClient.deletePostComment(commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
      if (activeCommentsPostId) {
        setPosts((prev) =>
          prev.map((p) =>
            p.id === activeCommentsPostId ? { ...p, comments_count: Math.max(0, p.comments_count - 1) } : p
          )
        );
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete comment');
    }
  };

  // Open User Profile
  const handleOpenProfile = async (userId: string) => {
    setViewingProfileId(userId);
    setIsLoadingProfile(true);
    setActiveFollowListTab(null);
    try {
      const [profile, uPosts] = await Promise.all([
        apiClient.getSocialProfile(userId),
        apiClient.getUserSocialPosts(userId),
      ]);
      setProfileData(profile);
      setProfilePosts(uPosts);
    } catch (err: any) {
      alert(err.message || 'Failed to load profile');
      setViewingProfileId(null);
    } finally {
      setIsLoadingProfile(false);
    }
  };

  // Toggle Follow from Profile Modal
  const handleToggleFollow = async () => {
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    if (!profileData || profileData.is_self || isFollowToggling) return;

    setIsFollowToggling(true);
    const wasFollowing = profileData.is_following;
    try {
      if (wasFollowing) {
        await apiClient.unfollowUser(profileData.id);
        setProfileData({
          ...profileData,
          is_following: false,
          followers_count: Math.max(0, profileData.followers_count - 1),
        });
      } else {
        await apiClient.followUser(profileData.id);
        setProfileData({
          ...profileData,
          is_following: true,
          followers_count: profileData.followers_count + 1,
        });
      }
    } catch (err: any) {
      alert(err.message || 'Failed to update follow status');
    } finally {
      setIsFollowToggling(false);
    }
  };

  // View Followers / Following lists
  const handleViewFollowList = async (type: 'followers' | 'following') => {
    if (!profileData) return;
    setActiveFollowListTab(type);
    setIsLoadingFollowList(true);
    try {
      const list =
        type === 'followers'
          ? await apiClient.listFollowers(profileData.id)
          : await apiClient.listFollowing(profileData.id);
      setFollowListUsers(list);
    } catch (err: any) {
      alert(err.message || `Failed to load ${type}`);
    } finally {
      setIsLoadingFollowList(false);
    }
  };

  // Open Report Modal
  const handleOpenReport = (id: string, type: 'post' | 'user' | 'comment') => {
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    setReportingTarget({ id, type });
    setReportReason('spam');
    setReportDescription('');
    setReportSuccessMessage(null);
  };

  // Submit Report
  const handleSubmitReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reportingTarget || isSubmittingReport) return;

    setIsSubmittingReport(true);
    try {
      await apiClient.reportContent({
        target_type: reportingTarget.type,
        target_id: reportingTarget.id,
        reason: reportReason,
        description: reportDescription.trim() || undefined,
      });
      setReportSuccessMessage('Thank you. Your report has been submitted to moderators.');
      setTimeout(() => {
        setReportingTarget(null);
        setReportSuccessMessage(null);
      }, 1800);
    } catch (err: any) {
      alert(err.message || 'Failed to submit report');
    } finally {
      setIsSubmittingReport(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto w-full space-y-5 pb-12">
      {/* Navigation Tabs: Discovery, Following, Reels, Explore, Profile */}
      <div className="flex items-center justify-between p-1.5 rounded-2xl bg-slate-900/60 border border-white/10 backdrop-blur-md overflow-x-auto scrollbar-none">
        <div className="flex space-x-1 w-full min-w-max">
          <button
            onClick={() => {
              setFeedMode('discovery');
              startTransition(() => {});
            }}
            className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition flex items-center space-x-1.5 ${
              feedMode === 'discovery'
                ? 'bg-violet-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            <span>Feed</span>
          </button>
          <button
            onClick={() => {
              if (!isAuthenticated) {
                openLoginModal();
                return;
              }
              setFeedMode('following');
              startTransition(() => {});
            }}
            className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition flex items-center space-x-1.5 ${
              feedMode === 'following'
                ? 'bg-violet-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span>Following</span>
          </button>
          <button
            onClick={() => {
              setFeedMode('reels');
              startTransition(() => {});
            }}
            className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition flex items-center space-x-1.5 ${
              feedMode === 'reels'
                ? 'bg-gradient-to-r from-pink-600 to-purple-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Reels</span>
          </button>
          <button
            onClick={() => {
              setFeedMode('explore');
              startTransition(() => {});
            }}
            className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition flex items-center space-x-1.5 ${
              feedMode === 'explore'
                ? 'bg-violet-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            <span>Explore</span>
          </button>
          {isAuthenticated && user && (
            <button
              onClick={() => {
                handleOpenProfile(user.id);
              }}
              className="px-3 py-1.5 text-xs font-semibold rounded-xl transition flex items-center space-x-1.5 text-slate-400 hover:text-slate-200 hover:bg-white/5"
            >
              <User className="w-3.5 h-3.5" />
              <span>Profile</span>
            </button>
          )}
        </div>
        <button
          onClick={() => fetchFeed(feedMode)}
          disabled={isLoadingFeed}
          className="p-2 ml-1 text-slate-400 hover:text-white rounded-xl hover:bg-white/5 transition shrink-0"
          title="Refresh"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoadingFeed ? 'animate-spin text-violet-400' : ''}`} />
        </button>
      </div>

      {/* VIEW MODES: REELS vs EXPLORE vs FEED */}
      {feedMode === 'reels' ? (
        /* REELS VERTICAL SHORT-VIDEO FEED */
        <div className="space-y-4">
          {posts.filter(p => p.media_type === 'video' || (p.media_url && anyVideoExtension(p.media_url))).length === 0 ? (
            <div className="text-center py-20 bg-slate-900/40 rounded-3xl border border-white/5 p-8 space-y-3">
              <Film className="w-12 h-12 text-slate-600 mx-auto" />
              <h3 className="text-sm font-semibold text-slate-300">No Reels Available Yet</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Upload a short video via the composer above to start the SUPER_AI Reels feed!
              </p>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-6">
              {posts.filter(p => p.media_type === 'video' || (p.media_url && anyVideoExtension(p.media_url))).map((reel, idx) => (
                <div
                  key={reel.id}
                  className="relative w-full max-w-sm rounded-3xl overflow-hidden bg-black border border-white/10 shadow-2xl aspect-[9/16] flex flex-col justify-between"
                >
                  {/* Reel Video Player */}
                  <video
                    src={reel.media_url || reel.image_url || undefined}
                    loop
                    playsInline
                    muted={isReelMuted}
                    autoPlay={idx === activeReelIndex}
                    className="absolute inset-0 w-full h-full object-cover"
                    onClick={() => setIsReelPlaying(!isReelPlaying)}
                  />

                  {/* Top Overlay Controls */}
                  <div className="relative z-10 p-4 flex items-center justify-between bg-gradient-to-b from-black/80 to-transparent">
                    <span className="text-[11px] font-bold text-white tracking-wider flex items-center space-x-1">
                      <Film className="w-3.5 h-3.5 text-pink-400" />
                      <span>REELS</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsReelMuted(!isReelMuted)}
                      className="p-2 rounded-full bg-black/50 text-white hover:bg-black/70 backdrop-blur-sm transition"
                    >
                      {isReelMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                    </button>
                  </div>

                  {/* Right-Side Interactive Actions Floating Stack */}
                  <div className="absolute right-3 bottom-20 z-20 flex flex-col items-center space-y-4 text-white">
                    <button
                      onClick={() => handleToggleLike(reel.id)}
                      className="flex flex-col items-center space-y-1 p-2 rounded-full bg-black/40 backdrop-blur-md hover:bg-black/60 transition"
                    >
                      <Heart className={`w-6 h-6 ${reel.is_liked ? 'text-pink-500 fill-current' : 'text-white'}`} />
                      <span className="text-[10px] font-bold">{reel.likes_count}</span>
                    </button>
                    <button
                      onClick={() => handleOpenComments(reel.id)}
                      className="flex flex-col items-center space-y-1 p-2 rounded-full bg-black/40 backdrop-blur-md hover:bg-black/60 transition"
                    >
                      <MessageCircle className="w-6 h-6 text-white" />
                      <span className="text-[10px] font-bold">{reel.comments_count}</span>
                    </button>
                    <button
                      onClick={() => {
                        if (navigator.share) {
                          navigator.share({ title: `Reel by @${reel.author_username}`, url: window.location.href });
                        } else {
                          navigator.clipboard.writeText(`${window.location.origin}/post/${reel.id}`);
                          alert('Reel link copied!');
                        }
                      }}
                      className="flex flex-col items-center space-y-1 p-2 rounded-full bg-black/40 backdrop-blur-md hover:bg-black/60 transition"
                    >
                      <Share2 className="w-6 h-6 text-white" />
                      <span className="text-[10px]">Share</span>
                    </button>
                  </div>

                  {/* Bottom Creator Info & Caption Overlay */}
                  <div className="relative z-10 p-5 bg-gradient-to-t from-black/95 via-black/60 to-transparent space-y-2">
                    <button
                      onClick={() => handleOpenProfile(reel.author_id)}
                      className="flex items-center space-x-2.5 text-left"
                    >
                      {reel.author_avatar ? (
                        <img src={reel.author_avatar} alt={reel.author_full_name} className="w-9 h-9 rounded-full object-cover border border-white/20" />
                      ) : (
                        <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-pink-500 to-violet-500 text-white font-bold flex items-center justify-center text-xs">
                          {reel.author_username.slice(0, 2).toUpperCase()}
                        </div>
                      )}
                      <div>
                        <p className="text-xs font-bold text-white flex items-center gap-1">
                          {reel.author_full_name}
                          <span className="text-slate-400 font-normal">@{reel.author_username}</span>
                        </p>
                      </div>
                    </button>
                    <p className="text-xs text-slate-200 line-clamp-2">{reel.content}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : feedMode === 'explore' ? (
        /* EXPLORE & DISCOVERY GRID WITH LIVE USER/POST SEARCH */
        <div className="space-y-4">
          <div className="relative">
            <input
              type="text"
              placeholder="Search people and posts across SUPER_AI..."
              value={exploreQuery}
              onChange={async (e) => {
                const q = e.target.value;
                setExploreQuery(q);
                if (q.trim().length >= 2) {
                  setIsSearchingExplore(true);
                  try {
                    const res = await apiClient.searchPlatform(q.trim(), 'all', 20);
                    setExploreResults(res);
                  } catch {
                    setExploreResults(null);
                  } finally {
                    setIsSearchingExplore(false);
                  }
                } else {
                  setExploreResults(null);
                }
              }}
              className="w-full bg-slate-900/60 border border-white/10 rounded-2xl pl-10 pr-4 py-3 text-xs md:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-violet-500 backdrop-blur-md"
            />
            <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-3.5" />
            {isSearchingExplore && <Loader2 className="w-4 h-4 animate-spin text-violet-400 absolute right-3.5 top-3.5" />}
          </div>

          {exploreResults && exploreResults.results.length > 0 ? (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Search Results ({exploreResults.results.length})</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {exploreResults.results.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => {
                      if (item.result_type === 'person') {
                        handleOpenProfile(item.id);
                      }
                    }}
                    className="p-3 rounded-xl bg-slate-900/50 border border-white/5 hover:border-violet-500/30 transition cursor-pointer flex items-center space-x-3"
                  >
                    {item.avatar_url ? (
                      <img src={item.avatar_url} alt={item.title} className="w-10 h-10 rounded-full object-cover" />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-violet-600/30 text-violet-300 font-bold flex items-center justify-center text-xs uppercase">
                        {item.title.slice(0, 2)}
                      </div>
                    )}
                    <div className="overflow-hidden">
                      <p className="text-xs font-bold text-white truncate">{item.title}</p>
                      <p className="text-[11px] text-slate-400 truncate">{item.subtitle || item.excerpt}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Explore Media Grid</h4>
              <div className="grid grid-cols-3 gap-1.5 rounded-2xl overflow-hidden">
                {posts.filter(p => p.image_url || p.media_url).map((p) => (
                  <div
                    key={p.id}
                    onClick={() => handleOpenProfile(p.author_id)}
                    className="relative aspect-square bg-slate-950 overflow-hidden cursor-pointer group"
                  >
                    {p.media_type === 'video' || (p.media_url && anyVideoExtension(p.media_url)) ? (
                      <div className="relative w-full h-full flex items-center justify-center bg-slate-900">
                        <video src={p.media_url || p.image_url || undefined} className="w-full h-full object-cover opacity-80" />
                        <Film className="w-5 h-5 text-white/90 absolute top-2 right-2 drop-shadow" />
                      </div>
                    ) : (
                      <img
                        src={p.media_url || p.image_url || undefined}
                        alt="Explore"
                        className="w-full h-full object-cover group-hover:scale-105 transition duration-300"
                      />
                    )}
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center space-x-3 text-white text-xs font-bold">
                      <span className="flex items-center space-x-1">
                        <Heart className="w-3.5 h-3.5 fill-current text-pink-500" />
                        <span>{p.likes_count}</span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        /* STANDARD SOCIAL FEED (Discovery / Following) */
        <>
          {/* Post Composer Card */}
          <div className="p-4 rounded-2xl bg-slate-900/60 border border-white/10 backdrop-blur-md space-y-3">
            <div className="flex items-start space-x-3">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="Profile" className="w-10 h-10 rounded-full object-cover shrink-0 border border-white/10" />
              ) : (
                <div className="w-10 h-10 rounded-full bg-violet-600/30 text-violet-300 font-bold flex items-center justify-center shrink-0 border border-violet-500/20 text-xs uppercase">
                  {user?.username ? user.username.slice(0, 2) : 'ME'}
                </div>
              )}
              <div className="w-full space-y-2">
                <textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder={isAuthenticated ? "What's happening in your universe?" : "Sign in to post, like, and join the conversation..."}
                  rows={2}
                  maxLength={2000}
                  className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none pt-1"
                />
                {showImageInput && (
                  <div className="flex items-center space-x-2 pt-1">
                    <input
                      type="url"
                      placeholder="Paste direct media URL (https://...)"
                      value={newImageUrl}
                      onChange={(e) => {
                        setNewImageUrl(e.target.value);
                        setSelectedFile(null);
                      }}
                      className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setShowImageInput(false);
                        setNewImageUrl('');
                      }}
                      className="text-slate-400 hover:text-white text-xs"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}
                {selectedFile && (
                  <div className="flex items-center justify-between p-2 rounded-xl bg-violet-600/10 border border-violet-500/20 text-xs text-violet-300">
                    <span className="truncate max-w-[200px]">{selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)</span>
                    <button
                      type="button"
                      onClick={() => setSelectedFile(null)}
                      className="text-slate-400 hover:text-white"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                {newImageUrl && !selectedFile && (
                  <div className="relative rounded-xl overflow-hidden border border-white/10 max-h-48">
                    {anyVideoExtension(newImageUrl) ? (
                      <video src={newImageUrl} className="w-full h-full object-cover" controls />
                    ) : (
                      <img src={newImageUrl} alt="Preview" className="w-full h-full object-cover" />
                    )}
                  </div>
                )}
                {mediaUploadProgress && (
                  <div className="flex items-center space-x-2 text-[11px] text-violet-400 pt-1">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>{mediaUploadProgress}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/5">
              <div className="flex items-center space-x-2 text-slate-400">
                <label className="p-1.5 rounded-lg hover:text-violet-400 hover:bg-white/5 transition cursor-pointer flex items-center space-x-1" title="Upload Media File (Image / Video)">
                  <Upload className="w-4 h-4" />
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm,video/ogg,video/quicktime"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        setSelectedFile(file);
                        setNewImageUrl('');
                        setShowImageInput(false);
                      }
                    }}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setShowImageInput(!showImageInput);
                    setSelectedFile(null);
                  }}
                  className={`p-1.5 rounded-lg transition ${
                    showImageInput ? 'text-violet-400 bg-violet-500/10' : 'hover:text-violet-400 hover:bg-white/5'
                  }`}
                  title="Add Image or Video URL"
                >
                  <ImageIcon className="w-4 h-4" />
                </button>
                <span className="text-[10px] text-slate-500">
                  {newContent.length}/2000
                </span>
              </div>

              <button
                onClick={handleCreatePost}
                disabled={(!newContent.trim() && !selectedFile) || isSubmittingPost}
                className="px-4 py-1.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold disabled:opacity-40 transition shadow flex items-center space-x-1.5"
              >
                {isSubmittingPost ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Posting...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Publish</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Feed Status Messages */}
          {feedError && (
            <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{feedError}</span>
            </div>
          )}

          {isLoadingFeed && (
            <div className="flex flex-col items-center justify-center py-12 space-y-2 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
              <span className="text-xs">Loading social feed...</span>
            </div>
          )}

          {!isLoadingFeed && posts.length === 0 && (
            <div className="text-center py-12 bg-slate-900/40 rounded-2xl border border-white/5 p-6 space-y-2">
              <p className="text-sm font-semibold text-slate-300">
                {feedMode === 'following' ? "You aren't following anyone with posts yet." : "No posts found in feed."}
              </p>
              <p className="text-xs text-slate-500">
                {feedMode === 'following'
                  ? "Switch to Discovery to explore creators and follow interesting accounts!"
                  : "Be the first to publish a post and share with the community."}
              </p>
            </div>
          )}

          {/* Feed Posts */}
          <div className="space-y-4">
            {posts.map((post) => {
              const isEditing = editingPostId === post.id;
              return (
                <div
                  key={post.id}
                  className="p-5 rounded-2xl bg-slate-900/50 border border-white/5 space-y-3 hover:border-white/15 transition relative group"
                >
                  {/* Post Header */}
                  <div className="flex items-start justify-between">
                    <button
                      type="button"
                      onClick={() => handleOpenProfile(post.author_id)}
                      className="flex items-center space-x-3 text-left focus:outline-none"
                    >
                      {post.author_avatar ? (
                        <img
                          src={post.author_avatar}
                          alt={post.author_full_name}
                          className="w-10 h-10 rounded-full object-cover shrink-0 border border-white/10"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-slate-800 text-slate-300 font-bold flex items-center justify-center shrink-0 border border-white/10 text-xs uppercase">
                          {post.author_username.slice(0, 2)}
                        </div>
                      )}
                      <div>
                        <h4 className="text-xs font-bold text-white flex items-center gap-1.5 hover:underline">
                          {post.author_full_name}
                          <span className="text-slate-500 font-normal">@{post.author_username}</span>
                        </h4>
                        <span className="text-[10px] text-slate-400">
                          {new Date(post.created_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                          {post.is_edited && <span className="text-slate-500 italic ml-1">(edited)</span>}
                        </span>
                      </div>
                    </button>

                    {/* Actions Dropdown / Menu buttons */}
                    <div className="flex items-center space-x-1">
                      {post.is_owner ? (
                        <>
                          <button
                            onClick={() => handleStartEdit(post)}
                            className="p-1.5 text-slate-400 hover:text-violet-400 rounded-lg hover:bg-white/5 transition"
                            title="Edit post"
                          >
                            <Edit3 className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDeletePost(post.id)}
                            className="p-1.5 text-slate-400 hover:text-rose-400 rounded-lg hover:bg-white/5 transition"
                            title="Delete post"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleOpenReport(post.id, 'post')}
                          className="p-1.5 text-slate-500 hover:text-amber-400 rounded-lg hover:bg-white/5 transition"
                          title="Report post"
                        >
                          <Flag className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Post Content */}
                  {isEditing ? (
                    <div className="space-y-2 pt-1">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        rows={3}
                        maxLength={2000}
                        className="w-full bg-slate-800/80 border border-violet-500/40 rounded-xl p-3 text-xs md:text-sm text-slate-100 focus:outline-none"
                      />
                      <input
                        type="url"
                        placeholder="Image URL"
                        value={editImageUrl}
                        onChange={(e) => setEditImageUrl(e.target.value)}
                        className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-slate-200"
                      />
                      <div className="flex justify-end space-x-2 pt-1">
                        <button
                          type="button"
                          onClick={() => setEditingPostId(null)}
                          className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSaveEdit(post.id)}
                          disabled={isSavingEdit || !editContent.trim()}
                          className="px-3 py-1 bg-violet-600 hover:bg-violet-500 text-white rounded-xl text-xs font-semibold disabled:opacity-40"
                        >
                          {isSavingEdit ? 'Saving...' : 'Save Changes'}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs md:text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">{post.content}</p>
                  )}

                  {/* Post Media Attachment */}
                  {!isEditing && (post.media_url || post.image_url) && (
                    <div className="rounded-xl overflow-hidden border border-white/10 max-h-96 bg-black flex items-center justify-center">
                      {post.media_type === 'video' || (post.media_url && anyVideoExtension(post.media_url)) ? (
                        <video
                          src={post.media_url || post.image_url || undefined}
                          controls
                          playsInline
                          className="w-full max-h-96 object-contain"
                        />
                      ) : (
                        <img
                          src={post.media_url || post.image_url || undefined}
                          alt="Attachment"
                          className="w-full h-auto object-cover max-h-96"
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      )}
                    </div>
                  )}

                  {/* Post Bottom Bar */}
                  <div className="flex items-center justify-between pt-2 text-slate-400 text-xs border-t border-white/5">
                    <button
                      onClick={() => handleToggleLike(post.id)}
                      className={`flex items-center space-x-1.5 transition ${
                        post.is_liked ? 'text-pink-500' : 'hover:text-pink-400'
                      }`}
                    >
                      <Heart className={`w-4 h-4 ${post.is_liked ? 'fill-current' : ''}`} />
                      <span>{post.likes_count}</span>
                    </button>

                    <button
                      onClick={() => handleOpenComments(post.id)}
                      className="flex items-center space-x-1.5 hover:text-blue-400 transition"
                    >
                      <MessageCircle className="w-4 h-4" />
                      <span>{post.comments_count}</span>
                    </button>

                    <button
                      onClick={() => {
                        if (navigator.share) {
                          navigator.share({ title: `Post by @${post.author_username}`, text: post.content, url: window.location.href });
                        } else {
                          navigator.clipboard.writeText(`${window.location.origin}/post/${post.id}`);
                          alert('Post link copied to clipboard!');
                        }
                      }}
                      className="hover:text-white transition flex items-center space-x-1"
                    >
                      <Share2 className="w-4 h-4" />
                      <span className="text-[10px]">Share</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* COMMENTS MODAL / DRAWER */}
      {activeCommentsPostId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col shadow-2xl">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <MessageCircle className="w-4 h-4 text-violet-400" />
                <span>Comments</span>
              </h3>
              <button
                onClick={() => setActiveCommentsPostId(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Comment List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {isLoadingComments ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
                </div>
              ) : comments.length === 0 ? (
                <div className="text-center py-8 text-slate-500 text-xs">
                  No comments yet. Start the conversation!
                </div>
              ) : (
                comments.map((comment) => (
                  <div key={comment.id} className="p-3 rounded-xl bg-white/5 border border-white/5 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        {comment.author_avatar ? (
                          <img src={comment.author_avatar} alt={comment.author_full_name} className="w-6 h-6 rounded-full object-cover" />
                        ) : (
                          <div className="w-6 h-6 rounded-full bg-violet-600/30 text-violet-300 font-bold flex items-center justify-center text-[10px] uppercase">
                            {comment.author_username.slice(0, 2)}
                          </div>
                        )}
                        <span className="text-xs font-semibold text-slate-200">
                          {comment.author_full_name}
                        </span>
                        <span className="text-[10px] text-slate-500">
                          @{comment.author_username}
                        </span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <span className="text-[10px] text-slate-500">
                          {new Date(comment.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                        {comment.is_owner ? (
                          <button
                            onClick={() => handleDeleteComment(comment.id)}
                            className="p-1 text-slate-500 hover:text-rose-400 transition"
                            title="Delete comment"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleOpenReport(comment.id, 'comment')}
                            className="p-1 text-slate-500 hover:text-amber-400 transition"
                            title="Report comment"
                          >
                            <Flag className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                    <p className="text-xs text-slate-300 pl-8 whitespace-pre-wrap">{comment.content}</p>
                  </div>
                ))
              )}
            </div>

            {/* Comment Composer */}
            <form onSubmit={handleCreateComment} className="p-3 border-t border-white/10 bg-slate-900/90 flex items-center space-x-2">
              <input
                type="text"
                placeholder={isAuthenticated ? "Write a comment..." : "Sign in to join the conversation"}
                value={newCommentText}
                onChange={(e) => setNewCommentText(e.target.value)}
                disabled={isSubmittingComment}
                maxLength={500}
                className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-violet-500"
              />
              <button
                type="submit"
                disabled={!newCommentText.trim() || isSubmittingComment}
                className="p-2 bg-violet-600 hover:bg-violet-500 text-white rounded-xl disabled:opacity-40 transition"
              >
                {isSubmittingComment ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* USER PROFILE MODAL */}
      {viewingProfileId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-lg max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Profile Header */}
            <div className="relative p-6 border-b border-white/10 bg-gradient-to-br from-violet-900/30 via-slate-900 to-slate-900">
              <button
                onClick={() => setViewingProfileId(null)}
                className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition"
              >
                <X className="w-5 h-5" />
              </button>

              {isLoadingProfile || !profileData ? (
                <div className="flex justify-center py-10">
                  <Loader2 className="w-6 h-6 animate-spin text-violet-400" />
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center space-x-4">
                      {profileData.avatar_url ? (
                        <img
                          src={profileData.avatar_url}
                          alt={profileData.full_name}
                          className="w-16 h-16 rounded-2xl object-cover border-2 border-violet-500/30 shadow-lg"
                        />
                      ) : (
                        <div className="w-16 h-16 rounded-2xl bg-violet-600/30 text-violet-300 font-bold flex items-center justify-center text-xl uppercase border-2 border-violet-500/20">
                          {profileData.username.slice(0, 2)}
                        </div>
                      )}
                      <div>
                        <h3 className="text-base font-bold text-white flex items-center gap-1.5">
                          {profileData.full_name}
                        </h3>
                        <p className="text-xs text-slate-400">@{profileData.username}</p>
                        <p className="text-[10px] text-slate-500 mt-1">
                          Joined {new Date(profileData.created_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}
                        </p>
                      </div>
                    </div>

                    {!profileData.is_self && (
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={handleToggleFollow}
                          disabled={isFollowToggling}
                          className={`px-4 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition ${
                            profileData.is_following
                              ? 'bg-white/10 hover:bg-rose-500/20 hover:text-rose-300 text-slate-200'
                              : 'bg-violet-600 hover:bg-violet-500 text-white shadow'
                          }`}
                        >
                          {profileData.is_following ? (
                            <>
                              <UserCheck className="w-3.5 h-3.5" />
                              <span>Following</span>
                            </>
                          ) : (
                            <>
                              <UserPlus className="w-3.5 h-3.5" />
                              <span>Follow</span>
                            </>
                          )}
                        </button>
                        <button
                          onClick={() => handleOpenReport(profileData.id, 'user')}
                          className="p-1.5 text-slate-400 hover:text-amber-400 rounded-lg hover:bg-white/5"
                          title="Report user"
                        >
                          <Flag className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>

                  {profileData.bio && (
                    <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap">
                      {profileData.bio}
                    </p>
                  )}

                  {/* Followers & Following Stats */}
                  <div className="flex items-center space-x-6 text-xs pt-1">
                    <button
                      onClick={() => handleViewFollowList('followers')}
                      className="hover:underline flex items-center space-x-1 text-slate-300"
                    >
                      <strong className="text-white">{profileData.followers_count}</strong>
                      <span className="text-slate-400">Followers</span>
                    </button>
                    <button
                      onClick={() => handleViewFollowList('following')}
                      className="hover:underline flex items-center space-x-1 text-slate-300"
                    >
                      <strong className="text-white">{profileData.following_count}</strong>
                      <span className="text-slate-400">Following</span>
                    </button>
                    <div className="flex items-center space-x-1 text-slate-300">
                      <strong className="text-white">{profileData.posts_count}</strong>
                      <span className="text-slate-400">Posts</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Profile Content Body: Follow list OR Posts */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {activeFollowListTab ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between border-b border-white/5 pb-2">
                    <button
                      onClick={() => setActiveFollowListTab(null)}
                      className="text-xs text-violet-400 hover:text-violet-300 flex items-center space-x-1"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      <span>Back to Posts</span>
                    </button>
                    <span className="text-xs font-semibold text-slate-300 capitalize">{activeFollowListTab}</span>
                  </div>

                  {isLoadingFollowList ? (
                    <div className="flex justify-center py-6">
                      <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
                    </div>
                  ) : followListUsers.length === 0 ? (
                    <div className="text-center py-6 text-xs text-slate-500">
                      No {activeFollowListTab} found.
                    </div>
                  ) : (
                    followListUsers.map((u) => (
                      <div
                        key={u.id}
                        onClick={() => handleOpenProfile(u.id)}
                        className="flex items-center justify-between p-2.5 rounded-xl bg-white/5 hover:bg-white/10 transition cursor-pointer"
                      >
                        <div className="flex items-center space-x-2.5">
                          {u.avatar_url ? (
                            <img src={u.avatar_url} alt={u.full_name} className="w-8 h-8 rounded-full object-cover" />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-violet-600/30 text-violet-300 font-bold flex items-center justify-center text-xs uppercase">
                              {u.username.slice(0, 2)}
                            </div>
                          )}
                          <div>
                            <p className="text-xs font-semibold text-slate-200">{u.full_name}</p>
                            <p className="text-[10px] text-slate-500">@{u.username}</p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Posts</h4>
                  {profilePosts.length === 0 ? (
                    <div className="text-center py-8 text-xs text-slate-500">
                      This user hasn't posted anything yet.
                    </div>
                  ) : (
                    profilePosts.map((post) => (
                      <div key={post.id} className="p-3.5 rounded-xl bg-white/5 border border-white/5 space-y-2">
                        <span className="text-[10px] text-slate-500">
                          {new Date(post.created_at).toLocaleDateString()}
                        </span>
                        <p className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap">{post.content}</p>
                        {post.image_url && (
                          <img src={post.image_url} alt="Attachment" className="rounded-lg w-full max-h-48 object-cover border border-white/10" />
                        )}
                        <div className="flex items-center space-x-4 text-[11px] text-slate-400 pt-1">
                          <span className="flex items-center space-x-1">
                            <Heart className={`w-3.5 h-3.5 ${post.is_liked ? 'text-pink-500 fill-current' : ''}`} />
                            <span>{post.likes_count}</span>
                          </span>
                          <span className="flex items-center space-x-1">
                            <MessageCircle className="w-3.5 h-3.5" />
                            <span>{post.comments_count}</span>
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ABUSE REPORTING MODAL */}
      {reportingTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-md p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Flag className="w-4 h-4 text-amber-400" />
                <span className="capitalize">Report {reportingTarget.type}</span>
              </h3>
              <button
                onClick={() => setReportingTarget(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {reportSuccessMessage ? (
              <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs text-center">
                {reportSuccessMessage}
              </div>
            ) : (
              <form onSubmit={handleSubmitReport} className="space-y-3">
                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Reason</label>
                  <select
                    value={reportReason}
                    onChange={(e) => setReportReason(e.target.value)}
                    className="w-full bg-slate-800 border border-white/10 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                  >
                    <option value="spam">Spam or unwanted advertising</option>
                    <option value="harassment">Harassment or hate speech</option>
                    <option value="misinformation">Misinformation or fake content</option>
                    <option value="inappropriate">Inappropriate or abusive material</option>
                    <option value="other">Other policy violation</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs text-slate-400">Optional details</label>
                  <textarea
                    value={reportDescription}
                    onChange={(e) => setReportDescription(e.target.value)}
                    placeholder="Provide additional context for reviewers..."
                    rows={3}
                    maxLength={500}
                    className="w-full bg-slate-800 border border-white/10 rounded-xl p-2.5 text-xs text-slate-200 focus:outline-none focus:border-violet-500 resize-none"
                  />
                </div>

                <div className="flex justify-end space-x-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setReportingTarget(null)}
                    className="px-4 py-2 text-xs text-slate-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmittingReport}
                    className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold disabled:opacity-50 transition"
                  >
                    {isSubmittingReport ? 'Submitting...' : 'Submit Report'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
