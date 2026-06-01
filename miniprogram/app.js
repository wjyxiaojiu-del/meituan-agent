// app.js
const config = require('./config');

App({
  onLaunch() {
    console.log('美团 AI 助手启动');

    // 获取系统信息
    const systemInfo = wx.getSystemInfoSync();
    this.globalData.systemInfo = systemInfo;
    this.globalData.statusBarHeight = systemInfo.statusBarHeight;
  },

  globalData: {
    // API 基础地址（从 config.js 读取，可在 config.js 中修改）
    baseUrl: config.baseUrl || 'http://localhost:8080',

    // 用户信息
    userInfo: null,

    // 会话 ID
    sessionId: null,

    // 系统信息
    systemInfo: null,
    statusBarHeight: 0
  }
});
