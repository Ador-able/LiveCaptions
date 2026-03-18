import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { FileVideo, Settings2, Loader2 } from 'lucide-react';

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { taskApi } from '@/lib/api';

const VALID_EXTENSIONS = [
  '.mp4',
  '.mkv',
  '.avi',
  '.mov',
  '.wmv',
  '.flv',
  '.webm',
  '.m4v',
  '.mp3',
  '.wav',
  '.m4a',
  '.aac',
  '.flac',
  '.ogg',
];

const SOURCE_LANGUAGES = [
  { value: 'auto', label: '自动检测' },
  { value: 'en', label: '英语 (English)' },
  { value: 'zh', label: '中文 (Chinese)' },
  { value: 'ja', label: '日语 (Japanese)' },
  { value: 'ko', label: '韩语 (Korean)' },
];

const TARGET_LANGUAGES = [
  { value: 'zh', label: '简体中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
];

interface FormData {
  file_path: string;
  source_language: string;
  target_language: string;
  video_description: string;
  llm_config: {
    api_key: string;
    base_url: string;
    model: string;
  };
  auto_save_subtitle: boolean;
  use_word_timestamps: boolean;
}

export default function NewTask() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState<FormData>({
    file_path: '',
    source_language: 'auto',
    target_language: 'zh',
    video_description: '',
    llm_config: {
      api_key: '',
      base_url: '',
      model: '',
    },
    auto_save_subtitle: true,
    use_word_timestamps: true,
  });

  const cleanFilePath = (path: string): string => {
    let cleaned = path.trim();
    if ((cleaned.startsWith('"') && cleaned.endsWith('"')) ||
        (cleaned.startsWith("'") && cleaned.endsWith("'"))) {
      cleaned = cleaned.slice(1, -1).trim();
    }
    return cleaned;
  };

  const validateForm = (): boolean => {
    const cleanedPath = cleanFilePath(formData.file_path);
    if (!cleanedPath) {
      toast.error('请输入视频文件路径');
      return false;
    }

    const hasValidExtension = VALID_EXTENSIONS.some(ext =>
      cleanedPath.toLowerCase().endsWith(ext)
    );
    if (!hasValidExtension) {
      toast.error(`不支持的文件格式。支持的格式：${VALID_EXTENSIONS.join(', ')}`);
      return false;
    }

    if (formData.llm_config.api_key) {
      if (formData.llm_config.api_key.length < 20) {
        toast.error('API Key格式不正确，长度过短');
        return false;
      }

      if (formData.llm_config.base_url) {
        try {
          const url = new URL(formData.llm_config.base_url);
          if (!['http:', 'https:'].includes(url.protocol)) {
            toast.error('Base URL必须使用http或https协议');
            return false;
          }
        } catch {
          toast.error('Base URL格式不正确');
          return false;
        }
      }

      if (!formData.llm_config.model.trim()) {
        toast.error('请输入模型名称');
        return false;
      }
    }

    return true;
  };

  const handleCreate = async () => {
    if (!validateForm()) return;

    setLoading(true);
    try {
      const formDataPayload = new FormData();
      const cleanedPath = cleanFilePath(formData.file_path);
      formDataPayload.append('video_path', cleanedPath);
      formDataPayload.append('source_language', formData.source_language);
      formDataPayload.append('target_language', formData.target_language);
      formDataPayload.append('video_description', formData.video_description);
      formDataPayload.append('auto_save_subtitle', String(formData.auto_save_subtitle));
      formDataPayload.append('use_word_timestamps', String(formData.use_word_timestamps));
      
      if (formData.llm_config.api_key) {
        formDataPayload.append('api_key', formData.llm_config.api_key);
      }
      if (formData.llm_config.base_url) {
        formDataPayload.append('base_url', formData.llm_config.base_url);
      }
      if (formData.llm_config.model) {
        formDataPayload.append('model', formData.llm_config.model);
      }
      
      const task = await taskApi.create(formDataPayload);
      toast.success('任务创建成功');
      navigate(`/tasks/${task.id}`);
    } catch (error) {
      toast.error('创建任务失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-in fade-in-50 slide-in-from-bottom-4">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">新建任务</h2>
        <p className="text-muted-foreground">处理一个新的视频文件以生成多语言字幕。</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务配置</CardTitle>
          <CardDescription>配置视频源和翻译选项。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="file_path">视频文件路径 (绝对路径)</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <FileVideo className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="file_path"
                  placeholder="e:\Videos\movie.mp4"
                  className="pl-9"
                  value={formData.file_path}
                  onChange={(e) => setFormData({ ...formData, file_path: e.target.value })}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">请输入服务端文件系统上的绝对路径。</p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>源语言</Label>
              <Select
                value={formData.source_language}
                onValueChange={(v) => setFormData({ ...formData, source_language: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择语言" />
                </SelectTrigger>
                <SelectContent>
                  {SOURCE_LANGUAGES.map((lang) => (
                    <SelectItem key={lang.value} value={lang.value}>
                      {lang.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>目标语言</Label>
              <Select
                value={formData.target_language}
                onValueChange={(v) => setFormData({ ...formData, target_language: v })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择语言" />
                </SelectTrigger>
                <SelectContent>
                  {TARGET_LANGUAGES.map((lang) => (
                    <SelectItem key={lang.value} value={lang.value}>
                      {lang.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-4 rounded-md border p-4 bg-muted/50">
            <div className="flex items-center gap-2">
              <Settings2 className="h-4 w-4" />
              <Label className="text-base">LLM 配置 (可选)</Label>
            </div>
            <p className="text-xs text-muted-foreground">如果不填写，将使用服务器环境变量中的配置。</p>

            <div className="grid gap-4">
              <div className="space-y-2">
                <Label htmlFor="api_key">API Key</Label>
                <Input
                  id="api_key"
                  type="password"
                  placeholder="sk-..."
                  value={formData.llm_config.api_key}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      llm_config: { ...formData.llm_config, api_key: e.target.value },
                    })
                  }
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="base_url">Base URL</Label>
                  <Input
                    id="base_url"
                    placeholder="https://api.openai.com/v1"
                    value={formData.llm_config.base_url}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        llm_config: { ...formData.llm_config, base_url: e.target.value },
                      })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="model">Model</Label>
                  <Input
                    id="model"
                    placeholder="gpt-4o"
                    value={formData.llm_config.model}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        llm_config: { ...formData.llm_config, model: e.target.value },
                      })
                    }
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4 rounded-md border p-4 bg-muted/50">
            <div className="space-y-2">
              <Label className="text-base">视频简介/背景信息 (可选)</Label>
              <p className="text-xs text-muted-foreground">
                提供视频的简介或背景信息，帮助 AI 更好地理解内容，提升翻译质量。
              </p>
              <textarea
                className="flex min-h-[100px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="输入视频简介，例如：这是一部关于太空探索的科幻电影..."
                value={formData.video_description}
                onChange={(e) => setFormData({ ...formData, video_description: e.target.value })}
              />
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="auto_save_subtitle"
              checked={formData.auto_save_subtitle}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, auto_save_subtitle: checked as boolean })
              }
            />
            <Label htmlFor="auto_save_subtitle" className="text-sm font-normal cursor-pointer">
              字幕生成后自动保存至视频文件夹内
            </Label>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="use_word_timestamps"
              checked={formData.use_word_timestamps}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, use_word_timestamps: checked as boolean })
              }
            />
            <Label htmlFor="use_word_timestamps" className="text-sm font-normal cursor-pointer">
              使用词时间戳 (更精确的字幕时间)
            </Label>
          </div>
        </CardContent>
        <CardFooter className="justify-end gap-2">
          <Button variant="ghost" onClick={() => navigate('/')}>
            取消
          </Button>
          <Button onClick={handleCreate} disabled={loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            创建任务
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
