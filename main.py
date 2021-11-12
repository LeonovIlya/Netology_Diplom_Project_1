import json
from collections import deque
from dataclasses import dataclass
import requests

vk_token = "_"
yandex_disk_folder_name = "vk_images"
output_json_name = "data.json"
album_id = -6

user_id = input("Введите ID пользователя ВК: ")
yandex_token = input("Введите token для yandex disk: ")


class PhotosInfoReceiver:
    def __init__(self, token, logger):
        self._token = token
        self._base_url = "https://api.vk.com/method"
        self._logger = logger

    def get_album_photos(self, user_id, album_id):
        result = requests.get(
            f"{self._base_url}/photos.get?owner_id={user_id}&access_token={self._token}&v=5.131&album_id={album_id}&photo_sizes=1&extended=1")
        result = json.loads(result.text)

        if "error" in result:
            error = ErrorDecoder.decode_error(result)
            self._logger.error(
                f"Ошибка получения фотографий пользователя {user_id} из альбома {album_id}. Код ошибки: {error.error_code}, Сообщение: {error.error_message}")
        else:
            return result
        return None

    def get_highest_resolution_album_photos(self, user_id, album_id):
        photos = deque()
        # получаем общий список фотографий
        vk_photos = self.get_album_photos(user_id, album_id)
        if vk_photos is not None:
            self._logger.success(f"Фотографии профиля {user_id} из альбома {album_id} получены")
            for item in vk_photos["response"]["items"]:
                likes_count = item["likes"]["count"]
                # получаем фото высшего качества, оно последнее
                highest_resolution_photo = item["sizes"][len(item["sizes"]) - 1]
                size_h = highest_resolution_photo["height"]
                size_w = highest_resolution_photo["width"]
                photo_url = highest_resolution_photo["url"]
                photos.append(Photo(photo_url, likes_count, album_id, size_h, size_w))
        return photos


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
    def __init__(self, token, logger):
        self._token = token
        self._resources_url = "https://cloud-api.yandex.net/v1/disk/resources/"
        self._upload_url = "https://cloud-api.yandex.net/v1/disk/resources/upload/"
        self._request_headers = {
            "Accept": "application/json",
            "Authorization": "OAuth " + token
        }
        self._logger = logger

    def upload_data_by_url(self, data_url, output_name, folder_name):
        if self.create_folder(folder_name):

            params = {
                'path': f'{folder_name}/{output_name}.jpg',
                'url': data_url,
                'overwrite': True
            }

            r = requests.post(url=self._upload_url, params=params, headers=self._request_headers)
            res = r.json()
            if "error" in res:
                if res["error"] == "UnauthorizedError":
                    self._logger.error(
                        f"Ошибка загрузки файла {output_name} в папку {folder_name} с url: {data_url}. Причина: "
                        f"ошибка авторизации. Проверьте токен.")
                    return False

    def create_folder(self, folder_name):
        request_params = {
            'path': folder_name
        }
        r = requests.put(url=self._resources_url, params=request_params, headers=self._request_headers)
        res = r.json()
        if "error" in res:
            if res["error"] == "UnauthorizedError":
                self._logger.error(
                    f"Ошибка создания папки {folder_name}. Причина: ошибка авторизации. Проверьте токен.")
                return False
        return True


class Logger:
    def __init__(self, enabled, error_tag, info_tag, success_tag):
        self._error_tag = error_tag
        self._info_tag = info_tag
        self._success_tag = success_tag
        self._enabled = enabled

    def error(self, message):
        if self._enabled:
            print(f"{self._error_tag}: {message}")

    def success(self, message):
        if self._enabled:
            print(f"{self._success_tag}: {message}")

    def info(self, message):
        if self._enabled:
            print(f"{self._info_tag}: {message}")


logger = Logger(True, "[ОШИБКА]", "[ИНФОРМАЦИЯ]", "[УСПЕШНО]")

vk_info_receiver = PhotosInfoReceiver(vk_token, logger)
data_uploader = DiskManager(yandex_token, logger)

photos = vk_info_receiver.get_highest_resolution_album_photos(user_id, album_id)

output_json = []

logger.info(f"Пользователь {user_id} имеет {len(photos)} фотографий в своем профиле")

for photo in photos:
    logger.info(f"Загрузка фотографии по пути {yandex_disk_folder_name}/{photo.likes_count}.jpg")
    data_uploader.upload_data_by_url(photo.url, photo.likes_count, yandex_disk_folder_name)
    # добавляем в json-массив данные о фотографии
    output_json.append({"file_name": f"{photo.likes_count}.jpg", "size": f"H:{photo.size_h}*W:{photo.size_w}"})

logger.success(
    f"Фотографии пользователя {user_id} в количестве {len(photos)} штук(и) загружены в папку {yandex_disk_folder_name} яндекс диска.")

# сохраняем json-файл
with open(output_json_name, 'w') as f:
    json.dump(output_json, f)
    logger.success(f"Json-файл сохранен с именем: {output_json_name}")
