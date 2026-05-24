#version 320 es

precision highp float;

layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aTexCoord;

out vec2 texcoord;

uniform vec2 cameraPos;
uniform float cameraScale;
uniform vec2 windowSize;
uniform vec2 screenshotSize;

vec2 to_world(vec2 v) {
    vec2 ratio = vec2(
        windowSize.x / screenshotSize.x / cameraScale,
        windowSize.y / screenshotSize.y / cameraScale);
    return vec2((v.x / screenshotSize.x * 2.0 - 1.0) / ratio.x,
                (v.y / screenshotSize.y * 2.0 - 1.0) / ratio.y);
}

void main()
{
    gl_Position = vec4(to_world(aPos - cameraPos * vec2(1.0, -1.0)), 0.0, 1.0);
    texcoord = aTexCoord;
}
