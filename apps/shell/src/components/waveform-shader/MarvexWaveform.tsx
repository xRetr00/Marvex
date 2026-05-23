import { useEffect, useRef } from "react";

const VERT = `
attribute vec4 position;
void main() { gl_Position = position; }
`;

/*
 * Faithful port of UI_EXTERNAL_Helpers/waveform-shaders/mainsample.glsl.
 * Shadertoy globals are mapped to Marvex-owned uniforms:
 *   iResolution -> resolution, iTime -> time,
 *   texelFetch(iChannel0,...).r -> audioLevel (the assistant-state amplitude).
 * Amplitude is fed from the assistant state and JS-smoothed so the wave
 * follows state instead of jumping randomly.
 */
const FRAG = `
precision mediump float;
uniform float time;
uniform vec2 resolution;
uniform float audioLevel;

const float PI = 3.14159265358;

vec4 smin(vec4 a, vec4 b, float k) {
    float h = clamp(0.5 + 0.5 * (a.w - b.w) / k, 0.0, 1.0);
    return mix(a, b, h) - k * h * (1.0 - h);
}

float luma(vec3 color) {
  return dot(color, vec3(0.299, 0.587, 0.114));
}

void main() {
    vec2 fragCoord = gl_FragCoord.xy;
    float min_res = min(resolution.x, resolution.y);
    vec2 uv = (fragCoord * 2.0 - resolution.xy) / min_res * 1.5;
    float t = time;
    const float w = 0.01; // Line Width
    const float f = 1.0;  // Frequency
    const float b = 60.0; // Bands
    float amp = 0.8 * audioLevel; // Amplitude (was iChannel0 sample)

    float xd = abs(uv.x);
    float falloff = (1.0 - exp(-xd * xd) + uv.x * uv.x * 0.05);
    vec4 d = vec4(vec3(0), 999999.0);
    float off = t * 2.0;
    float fm = (1.0 + 0.3 * sin(t));
    float x = uv.x * PI * f * fm - off;
    vec4 y1 = vec4(vec3(1.0, 0.0, 0.0), sin(x));
    vec4 y2 = vec4(vec3(0.0, 0.7, 1.0), sin(x + 1.0) * 0.5);
    vec4 y3 = vec4(vec3(1.0, 0.0, 1.0), sin(x + 1.8) * 1.1);
    vec4 y4 = vec4(vec3(0.0, 1.0, 1.0), sin(x + 3.0) * 0.7);
    float am = amp / (1.0 + xd * xd * 4.0);
    for (float i = 0.0; i <= 1.001; i += 1.0 / b) {
        vec4 yy1 = mix(y1, y2, i);
        vec4 yy2 = mix(y3, y4, i);
        vec4 y = mix(yy1, yy2, i);
        y.w = abs(uv.y - y.w * am) - w + falloff * 0.05;
        y.rgb *= y.rgb;
        d = smin(y, d, 0.05);
    }
    float a = 0.01;
    float c = smoothstep(a, -a, d.w);
    vec3 col = d.rgb * sqrt(c) * 0.5;
    col += pow(luma(col), 0.3) * 1.0;

    gl_FragColor = vec4(col, 1.0);
}
`;

interface MarvexWaveformProps {
  /** Target amplitude (0..1) derived from assistant state; JS-smoothed internally. */
  audioLevel: number;
  className?: string;
  width?: number;
  height?: number;
}

export function MarvexWaveform({ audioLevel, className, width = 320, height = 80 }: MarvexWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const startTimeRef = useRef<number>(performance.now());
  const targetRef = useRef<number>(audioLevel);
  const smoothRef = useRef<number>(audioLevel);

  useEffect(() => {
    targetRef.current = audioLevel;
  }, [audioLevel]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl");
    if (!gl) return;

    const compileShader = (type: number, src: string): WebGLShader | null => {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, src);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        console.warn("Waveform shader compile error:", gl.getShaderInfoLog(shader));
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    };

    const vs = compileShader(gl.VERTEX_SHADER, VERT);
    const fs = compileShader(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.warn("Waveform program link error:", gl.getProgramInfoLog(program));
      return;
    }
    gl.useProgram(program);

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const posLoc = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    const timeLoc = gl.getUniformLocation(program, "time");
    const resLoc = gl.getUniformLocation(program, "resolution");
    const audioLoc = gl.getUniformLocation(program, "audioLevel");

    const draw = () => {
      const elapsed = (performance.now() - startTimeRef.current) / 1000;
      // Smooth toward the state target so the wave follows state without
      // random jitter from raw audio frames.
      smoothRef.current += (targetRef.current - smoothRef.current) * 0.09;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(timeLoc, elapsed);
      gl.uniform2f(resLoc, canvas.width, canvas.height);
      gl.uniform1f(audioLoc, smoothRef.current);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      rafRef.current = requestAnimationFrame(draw);
    };
    draw();

    return () => {
      cancelAnimationFrame(rafRef.current);
      gl.deleteProgram(program);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={className}
      style={{ display: "block" }}
      aria-label="Marvex waveform"
    />
  );
}
