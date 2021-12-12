import json
import requests
import datetime
import os
from dataclasses import dataclass
from collections import deque


vk_token = ""
yandex_disk_folder_name = "vk_images"
output_json_name = "data.json"
output_logs_file = 'logs.txt'
album_id = -6

user_id = input("Введите ID пользователя ВК: ")
yandex_token = input("Введите token для yandex disk: ")


class PhotosInfoReceiver:
    def __init__(self, token, logger_object):
        self._token = token
        self._base_url = "https://api.vk.com/method"
        self._logger = logger_object

    def get_album_photos(self, u_id, a_id):
        try:
            result = requests.get(
                f"{self._base_url}/photos.get?owner_id={u_id}" +
                f"&access_token={self._token}" +
                f"&v=5.131&album_id={a_id}" +
                f"&photo_sizes=1&extended=1")
            result = json.loads(result.text)

            if "error" in result:
                error = ErrorDecoder.decode_error(result)
                self._logger.error(
                    f"Ошибка получения фотографий пользователя " +
                    f"{u_id} из альбома {a_id}." +
                    f"Код ошибки: {error.error_code}, " +
                    f"Сообщение: {error.error_message}")
            else:
                return result
        except Exception as e:
            self._logger.error(e)
        return None

    def get_highest_resolution_album_photos(self, u_id, a_id):
        photos_array = deque()
        # получаем общий список фотографий
        vk_photos = self.get_album_photos(u_id, a_id)
        if vk_photos is not None:
            self._logger.success(f"Фотографии профиля {u_id}" +
                                 f" из альбома {a_id} получены")
            for item in vk_photos["response"]["items"]:
                likes_count = item["likes"]["count"]
                # получаем фото высшего качества, оно последнее
                highest_resolution_photo = item["sizes"][len(item["sizes"]) - 1]
                size_h = highest_resolution_photo["height"]
                size_w = highest_resolution_photo["width"]
                photo_url = highest_resolution_photo["url"]
                u_photo = Photo(photo_url, likes_count, a_id, size_h, size_w)
                photos_array.append(u_photo)
        return photos_array


@dataclass(frozen=True)
class Photo:
    url: str
    likes_count: int
    album_id: int
    size_h: str
    size_w: str


@dataclass(frozen=True)
class Error:
    error_code: int
    error_message: str


class ErrorDecoder:
    @staticmethod
    def decode_error(message) -> Error:
        code = message["error"]["error_code"]
        msg = message["error"]["error_msg"]
        return Error(error_code=code, error_message=msg)


class DiskManager:
    def __init__(self, token, logger_object):
        self._token = token
        self._res_url = "https://cloud-api.yandex.net/v1/disk/resources/"
        self._up_url = "https://cloud-api.yandex.net/v1/disk/resources/upload/"
        self._headers = {
            "Accept": "application/json",
            "Authorization": "OAuth " + token
        }
        self._logger = logger_object

    def upload_data_by_url(self, data_url, output_name, folder_name):
        if self.create_folder(folder_name):
            params = {
                'path': f'{folder_name}/{output_name}.jpg',
                'url': data_url,
                'overwrite': True
            }
            try:
                r = requests.post(url=self._up_url, params=params, headers=self._headers)
                res = r.json()
                if "error" in res:
                    if res["error"] == "UnauthorizedError":
                        self._logger.error(
                            f"Ошибка загрузки файла {output_name}" +
                            f" в папку {folder_name} " +
                            f"с url: {data_url}. Причина: " +
                            f"ошибка авторизации. Проверьте токен.")
                        return False
                return True
            except Exception as e:
                self._logger.error(e)
        return False

    def create_folder(self, folder_name):
        r_params = {
            'path': folder_name
        }
        try:
            r = requests.put(url=self._res_url, params=r_params, headers=self._headers)
            res = r.json()
            if "error" in res:
                if res["error"] == "UnauthorizedError":
                    self._logger.error(
                        f"Ошибка создания папки {folder_name}. " +
                        f"Причина: ошибка авторизации." +
                        f" Проверьте токен.")
                    return False
            return True
        except Exception as e:
            self._logger.error(e)
        return False


class Logger:
    def __init__(self, enabled, error_tag, info_tag,
                 success_tag, file_log_enabled=False, file_log_path=''):
        self._error_tag = error_tag
        self._info_tag = info_tag
        self._success_tag = success_tag
        self._enabled = enabled
        self._file_log = file_log_enabled

        path = os.path.normpath(os.getcwd() + os.sep + os.pardir)

        path = path.replace('\\', '/')

        self._file_path = f'{path}/{file_log_path}'

    def _write_to_file(self, message):
        if self._file_log:
            message = f'[{datetime.datetime.now()}]: {message}'
            try:
                with open(self._file_path, 'a') as f:
                    f.write(message)
                    f.write('\n')
            except Exception as e:
                self.error(e)

    def error(self, message):
        if self._enabled:
            message = f"{self._error_tag}: {message}"
            print(message)
            self._write_to_file(message)

    def success(self, message):
        if self._enabled:
            message = f"{self._success_tag}: {message}"
            print(message)
            self._write_to_file(message)

    def info(self, message):
        if self._enabled:
            message = f"{self._info_tag}: {message}"
            print(message)
            self._write_to_file(message)


logger = Logger(True, "[ОШИБКА]", "[ИНФОРМАЦИЯ]", "[УСПЕШНО]", True, output_logs_file)

vk_receiver = PhotosInfoReceiver(vk_token, logger)
data_uploader = DiskManager(yandex_token, logger)


def main():
    photos = vk_receiver.get_highest_resolution_album_photos(user_id, album_id)

    output_json = []

    logger.info(f"Пользователь {user_id}" +
                f" имеет {len(photos)}" +
                f" фотографий в своем профиле")

    for photo in photos:
        logger.info(f"Загрузка фотографии по пути {yandex_disk_folder_name}" +
                    f"/{photo.likes_count}.jpg")
        data_uploader.upload_data_by_url(photo.url,
                                         photo.likes_count,
                                         yandex_disk_folder_name)
        # добавляем в json-массив данные о фотографии
        data = {"file_name": f"{photo.likes_count}.jpg",
                "size": f"H:{photo.size_h}*W:{photo.size_w}"}
        output_json.append(data)

    logger.success(
        f"Фотографии пользователя " +
        f"{user_id} в количестве {len(photos)} штук(и) загружены в папку " +
        f"{yandex_disk_folder_name} яндекс диска.")

    # сохраняем json-файл
    with open(output_json_name, 'w') as f:
        json.dump(output_json, f)
        logger.success(f"Json-файл сохранен с именем: {output_json_name}")


if __name__ == '__main__':
    main()