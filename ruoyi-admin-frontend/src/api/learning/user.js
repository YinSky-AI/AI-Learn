import request from '@/utils/request'

// 查询平台用户列表
export function listPlatformUser(query) {
  return request({
    url: '/learning/user/list',
    method: 'get',
    params: query
  })
}

// 查询平台用户详细
export function getPlatformUser(userId) {
  return request({
    url: '/learning/user/' + userId,
    method: 'get'
  })
}

// 修改平台用户
export function updatePlatformUser(data) {
  return request({
    url: '/learning/user',
    method: 'put',
    data: data
  })
}

// 删除平台用户
export function delPlatformUser(userId) {
  return request({
    url: '/learning/user/' + userId,
    method: 'delete'
  })
}