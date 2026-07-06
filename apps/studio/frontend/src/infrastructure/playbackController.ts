// HTMLMediaElement (Audio / Video) をラップした再生制御。
// store には依存せず、currentTime/playing/rate をコールバックで通知する (配線は app 側)。

import { nextPlaybackRate } from "../domain/playback.ts";

export class PlaybackController {
  private media: HTMLMediaElement = new Audio();
  /** 区間再生の停止時刻。null なら通常再生。 */
  private stopAt: number | null = null;
  private raf = 0;
  private warned = false;

  onTick: (t: number) => void = () => this.warnUnwired();
  onPlayingChange: (playing: boolean) => void = () => this.warnUnwired();
  onRateChange: (rate: number) => void = () => this.warnUnwired();

  private warnUnwired(): void {
    if (this.warned) return;
    this.warned = true;
    console.warn("[PlaybackController] not wired — call wirePlayback() at startup");
  }

  constructor() {
    this.media.addEventListener("ended", () => this.handleStop());
  }

  /** 現在の再生速度 (カバレッジ判定にも使う)。0.25〜1.5 倍。 */
  get rate(): number {
    return this.media.playbackRate;
  }

  /** 再生速度を1段上げ下げ (dir=+1 で速く / -1 で遅く)。両端でクランプし通知する。 */
  stepRate(dir: 1 | -1): void {
    const rate = nextPlaybackRate(this.media.playbackRate, dir);
    if (rate === this.media.playbackRate) return;
    this.media.playbackRate = rate;
    this.onRateChange(rate);
  }

  attach(url: string): void {
    this.media.src = url;
    this.stopAt = null;
    this.onTick(0);
  }

  /**
   * 動画ファイル読み込み時に <video> 要素に切り替える。
   * 音声ファイルに戻る場合は el=null で内部 Audio に差し戻す。
   */
  setMediaElement(el: HTMLVideoElement | null): void {
    const wasPlaying = !this.media.paused;
    const prevUrl = this.media.src;
    const prevTime = this.media.currentTime;
    const prevRate = this.media.playbackRate;
    cancelAnimationFrame(this.raf);

    this.media.removeEventListener("ended", this.handleStop);
    this.media = el ?? new Audio();
    this.media.addEventListener("ended", () => this.handleStop());

    if (prevUrl) this.media.src = prevUrl;
    this.media.currentTime = prevTime;
    this.media.playbackRate = prevRate; // 動画↔音声の切替で速度を保つ
    if (wasPlaying) void this.media.play();
  }

  toggle(): void {
    this.stopAt = null;
    if (this.media.paused) {
      if (this.media.ended) this.media.currentTime = 0;
      this.start();
    } else {
      this.pause();
    }
  }

  seek(t: number): void {
    this.media.currentTime = t;
    this.stopAt = null;
    this.onTick(t);
  }

  playFrom(start: number): void {
    this.stopAt = null;
    this.media.currentTime = start;
    this.start();
  }

  playRegion(start: number, end: number): void {
    this.stopAt = end;
    this.media.currentTime = start;
    this.start();
  }

  private start(): void {
    void this.media.play();
    this.onPlayingChange(true);
    this.tick();
  }

  private pause(): void {
    this.media.pause();
    this.onPlayingChange(false);
    cancelAnimationFrame(this.raf);
  }

  private handleStop(): void {
    this.onPlayingChange(false);
    cancelAnimationFrame(this.raf);
  }

  private tick = (): void => {
    const t = this.media.currentTime;
    this.onTick(t);
    if (this.stopAt !== null && t >= this.stopAt) {
      this.stopAt = null;
      this.pause();
      return;
    }
    if (!this.media.paused) this.raf = requestAnimationFrame(this.tick);
  };
}
