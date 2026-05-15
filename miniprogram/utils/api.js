// utils/api.js - API 请求封装

const app = getApp();

/**
 * 发送 Agent 请求
 * @param {string} userInput - 用户输入
 * @param {string} sessionId - 会话 ID（可选）
 * @returns {Promise}
 */
function executeAgent(userInput, sessionId) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/execute`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: {
        userInput: userInput,
        sessionId: sessionId || app.globalData.sessionId,
        userId: app.globalData.userInfo?.userId
      },
      success(res) {
        if (res.statusCode === 200) {
          const data = res.data;

          // 保存会话 ID
          if (data.sessionId) {
            app.globalData.sessionId = data.sessionId;
          }

          resolve(data);
        } else {
          reject(new Error(`请求失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

/**
 * 确认/取消方案
 * @param {string} sessionId - 会话 ID
 * @param {boolean} confirmed - 是否确认
 * @returns {Promise}
 */
function confirmPlan(sessionId, confirmed) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/confirm`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json'
      },
      data: {
        sessionId: sessionId,
        confirmed: confirmed
      },
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data);
        } else {
          reject(new Error(`确认请求失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

/**
 * 健康检查
 * @returns {Promise}
 */
function healthCheck() {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${app.globalData.baseUrl}/api/agent/health`,
      method: 'GET',
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data);
        } else {
          reject(new Error(`健康检查失败: ${res.statusCode}`));
        }
      },
      fail(err) {
        reject(err);
      }
    });
  });
}

module.exports = {
  executeAgent,
  confirmPlan,
  healthCheck
};
