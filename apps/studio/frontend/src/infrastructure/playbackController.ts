// HTMLMediaElement (Audio / Video) をラップした再生制御。
// store には依存せず、currentTime/playing をコールバックで通知する (配線は app 側)。

export class PlaybackController {
  private media: HTMLMediaElement = new Audio();
  /** 区間再生の停止時刻。null なら通常再生。 */
  private stopAt: number | null = null;
  private raf = 0;
  private warned = false;

  onTick: (t: number) => void = () => this.warnUnwired();
  onPlayingChange: (playing: boolean) => void = () => this.warnUnwired();

  private warnUnwired(): void {
    if (this.warned) return;
    this.warned = true;
    console.warn("[PlaybackController] not wired — call wirePlayback() at startup");
  }

  constructor() {
    this.media.addEventListener("ended", () => this.handleStop());
  }

  /** 現在の再生速度 (カバレッジ判定用)。倍速機能はまだ無いので通常 1。 */
  get rate(): number {
    return this.media.playbackRate;
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
    cancelAnimationFrame(this.raf);

    this.media.removeEventListener("ended", this.handleStop);
    this.media = el ?? new Audio();
    this.media.addEventListener("ended", () => this.handleStop());

    if (prevUrl) this.media.src = prevUrl;
    this.media.currentTime = prevTime;
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
