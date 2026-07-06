import { useState } from 'react'
import { FileText, Loader2 } from 'lucide-react'
import type { ThumbnailStatus } from '@/shared/types'
import { cn } from '@/lib/utils'

interface DocumentThumbnailProps {
  status: ThumbnailStatus | undefined
  url: string | null | undefined
  mimeType: string
  className?: string
  fit?: 'cover' | 'contain'
}

export function DocumentThumbnail({
  status,
  url,
  className,
  fit = 'cover',
}: DocumentThumbnailProps) {
  const [imgFailed, setImgFailed] = useState(false)

  if (status === 'ready' && url && !imgFailed) {
    return (
      <div className={cn('overflow-hidden rounded-md bg-muted', className)}>
        <img
          src={url}
          loading="lazy"
          alt=""
          className={cn('h-full w-full', fit === 'cover' ? 'object-cover' : 'object-contain')}
          onError={() => setImgFailed(true)}
        />
      </div>
    )
  }

  if (status === 'processing') {
    return (
      <div className={cn('flex items-center justify-center rounded-md bg-muted', className)}>
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className={cn('flex items-center justify-center rounded-md bg-muted', className)}>
      <FileText className="h-8 w-8 text-primary" />
    </div>
  )
}
