// app.js
App({
  onLaunch() {
    console.log('美团 AI 助手启动');

    // 获取系统信息
    const systemInfo = wx.getSystemInfoSync();
    this.globalData.systemInfo = systemInfo;
    this.globalData.statusBarHeight = systemInfo.statusBarHeight;
  },

  globalData: {
    // API 基础地址
    baseUrl: 'http://localhost:8080',

    // WebSocket 地址
    wsUrl: 'ws://localhost:8080/ws',

    // 用户信息
    userInfo: null,

    // 会话 ID
    sessionId: null,

    // 系统信息
    systemInfo: null,
    statusBarHeight: 0
  }
});
